# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Fans tile: ORIGAMI's curve on both fans while it is on, else the firmware's own."""

import asyncio
import logging
import threading
from collections.abc import Callable
from pathlib import Path

from origami.blocks import Context
from origami.fans import (
    POLL_SECONDS,
    Curve,
    FanCurve,
    Hold,
    curve_dir,
    curve_on,
    fan_speed,
    give_back,
    hold_curve,
    hold_fans,
    hottest,
    own_curve,
    write_curve,
)
from origami.settings import Settings
from origami.tasks import BackgroundTask

log = logging.getLogger(__name__)


class FansBlock:
    """Holds the fan curve; the power block writes its limits again when the fans go back.

    The firmware's own curve may bring back its platform profile's own power, so giving the fans
    back has the power keeper write its limits again (`limits_again`, safe from a worker thread)
    and look at once (`look`, on the event loop only). A temperature is held only on the consoles
    whose fans the hold knows (`board` names this one); on the others the curve follows its points.
    """

    def __init__(
        self,
        context: Context,
        *,
        limits_again: Callable[[str], None],
        look: Callable[[], None],
        board: Callable[[], str | None],
    ) -> None:
        self._context = context
        self._board = board
        self._limits_again = limits_again
        self._look = look
        self._curve: FanCurve | None = None
        """The curve of the settings followed last, which the keeper keeps in the firmware."""
        self._written: Curve | None = None
        """The curve last sent to the fans while ORIGAMI holds them."""
        self._holder: Hold | None = None
        """Finds the fans' level while the curve holds a temperature."""
        self._fans = threading.Lock()
        """One writer to the fans at a time. The keeper's write runs in a thread that a cancelled
        keeper leaves behind, so it looks under this lock whether the fans are still ORIGAMI's."""
        self._keeper = BackgroundTask("origami-fans", self._keep_curve)

    async def send(self, curve: FanCurve | None) -> None:
        """Send a changed curve before it is saved, so a curve the firmware refused is not kept."""
        root = self._context.root
        if curve is None or not curve.enabled or await asyncio.to_thread(curve_dir, root) is None:
            return
        owner = (await self._context.conflicts()).fans
        if owner is not None:
            raise RuntimeError(f"{owner} sets the fans, so ORIGAMI leaves them alone")
        await asyncio.to_thread(self._write, self._wanted(curve))

    async def follow(self, settings: Settings) -> None:
        """Hold the fan curve while it is on and no plugin drives the fans; else give them back."""
        root = self._context.root
        curve = self._curve = settings.fans
        owner = (await self._context.conflicts()).fans
        keep = (
            curve is not None
            and curve.enabled
            and owner is None
            and await asyncio.to_thread(curve_dir, root) is not None
        )
        if curve is None or not keep or not self._holds(curve):
            # The next hold starts afresh, not from the level this one was left at.
            self._holder = None
        if curve is not None and keep:
            try:
                await asyncio.to_thread(self._write_unless_there, self._wanted(curve))
            except OSError as error:
                log.warning("Fan curve not written: %s", error)
        elif await asyncio.to_thread(self.give_back, owner):
            # Set here, on the loop: an asyncio event is not for a worker thread to set.
            self._look()
        await self._keeper.run_while(on=keep)

    def held(self) -> Curve | None:
        """The curve in the firmware while ORIGAMI holds a temperature with it, for the screen."""
        curve = self._curve
        return self._written if curve is not None and curve.enabled and self._holds(curve) else None

    def give_back(self, owner: str | None) -> bool:
        """Let the firmware run the fans on its own curve again; blocks briefly.

        A plugin that drives the fans now keeps them as it set them: only ORIGAMI's record goes.
        Returns whether the firmware got them back, so the power keeper is to look at the limits.
        """
        journal = self._context.journal
        with self._fans:
            if not journal.recorded("fans", "curve"):
                return False
            if owner is not None:
                journal.forget("fans", "curve")
                self._written = None
                return False
            try:
                give_back(self._context.root)
            except OSError as error:
                log.warning("Fans not given back to the firmware: %s", error)
                return False
            journal.forget("fans", "curve")
            self._written = None
        self._limits_again("fans given back")
        log.info("Fans given back to the firmware")
        return True

    def stop(self) -> None:
        self._keeper.cancel()

    def _holds(self, curve: FanCurve) -> bool:
        """Whether the curve holds a temperature here: asked to, on a console whose fans can."""
        return curve.hold and hold_fans(self._board()) is not None

    def _wanted(self, curve: FanCurve) -> Curve:
        """The curve for the firmware now: the user's points, or the level found for the hold."""
        fans = hold_fans(self._board())
        if not curve.hold or fans is None:
            return own_curve(curve.points)
        if self._holder is None:
            self._holder = Hold(curve.target, fans)
        self._holder.aim(curve.target)
        return hold_curve(self._holder.held, self._holder.level)

    def _write(self, curve: Curve) -> None:
        """Send the curve to the fans; blocks briefly."""
        with self._fans:
            self._send(curve)

    def _write_unless_there(self, curve: Curve) -> None:
        """Send the curve unless the fans follow it already; blocks briefly."""
        with self._fans:
            if curve != self._written or not curve_on(self._context.root):
                self._send(curve)

    def _send(self, curve: Curve) -> None:
        journal = self._context.journal
        if not journal.recorded("fans", "curve"):
            # The fans ran the firmware's own curve before ORIGAMI, not a value.
            journal.record("fans", "curve", None)
        write_curve(self._context.root, curve)
        self._written = curve
        log.info("Fan curve written: %s", " ".join(f"{temp}/{speed}" for temp, speed in curve))

    async def _keep_curve(self) -> None:
        """Keep the curve in the firmware: on again whenever something switches it off, a platform
        profile, say, and moved as the temperature it holds asks."""
        root = self._context.root
        while True:
            await asyncio.sleep(POLL_SECONDS)
            curve, holder = self._curve, self._holder
            if curve is None or not curve.enabled:
                continue
            if holder is not None and self._holds(curve):
                temp, rpm = await asyncio.to_thread(_readings, root)
                # Unread, the curve in the firmware goes on by itself.
                if temp is not None:
                    holder.look(temp, rpm)
            if self._curve is not curve:
                # Changed over the look: the new settings were written as they came.
                continue
            try:
                await asyncio.to_thread(self._keep, curve, self._wanted(curve))
            except OSError as error:
                log.warning("Fan curve not written again: %s", error)

    def _keep(self, curve: FanCurve, wanted: Curve) -> None:
        """The keeper's write; blocks briefly.

        Nothing is written once these are not the settings followed or the fans went back.
        """
        root = self._context.root
        with self._fans:
            if self._curve is not curve or not self._context.journal.recorded("fans", "curve"):
                return
            moved = wanted != self._written
            if not moved and curve_on(root):
                return
            write_curve(root, wanted)
            self._written = wanted
            if not moved:
                log.info("Fan curve switched on again")


def _readings(root: Path) -> tuple[float | None, int | None]:
    """The SoC's temperature and fan 1's speed now, for a look of the hold; blocks briefly."""
    return hottest(root), fan_speed(root)
