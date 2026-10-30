# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Fans tile: ORIGAMI's curve on both fans while it is on, else the firmware's own."""

import asyncio
import logging
from collections.abc import Callable

from origami.blocks import Context
from origami.fans import POLL_SECONDS, FanCurve, curve_dir, curve_on, give_back, write_curve
from origami.settings import Settings
from origami.tasks import BackgroundTask

log = logging.getLogger(__name__)


class FansBlock:
    """Holds the fan curve; the power block writes its limits again when the fans go back.

    The firmware's own curve may bring back its platform profile's own power, so giving the fans
    back has the power keeper write its limits again (`limits_again`, safe from a worker thread)
    and look at once (`look`, on the event loop only).
    """

    def __init__(
        self, context: Context, *, limits_again: Callable[[str], None], look: Callable[[], None]
    ) -> None:
        self._context = context
        self._limits_again = limits_again
        self._look = look
        self._curve: FanCurve | None = None
        """The curve of the settings followed last, which the hold keeps on."""
        self._written: tuple[int, ...] | None = None
        """The points last sent to the fans while ORIGAMI holds them."""
        self._hold = BackgroundTask("origami-fans", self._hold_curve)

    async def send(self, curve: FanCurve | None) -> None:
        """Send a changed curve before it is saved, so a curve the firmware refused is not kept."""
        root = self._context.root
        if curve is None or not curve.enabled or await asyncio.to_thread(curve_dir, root) is None:
            return
        owner = (await self._context.conflicts()).fans
        if owner is not None:
            raise RuntimeError(f"{owner} sets the fans, so ORIGAMI leaves them alone")
        await asyncio.to_thread(self._write, curve.points)

    async def follow(self, settings: Settings) -> None:
        """Hold the fan curve while it is on and no plugin drives the fans; else give them back."""
        root = self._context.root
        curve = self._curve = settings.fans
        owner = (await self._context.conflicts()).fans
        hold = (
            curve is not None
            and curve.enabled
            and owner is None
            and await asyncio.to_thread(curve_dir, root) is not None
        )
        if curve is not None and hold:
            if curve.points != self._written or not await asyncio.to_thread(curve_on, root):
                try:
                    await asyncio.to_thread(self._write, curve.points)
                except OSError as error:
                    log.warning("Fan curve not written: %s", error)
        elif await asyncio.to_thread(self.give_back, owner):
            # Set here, on the loop: an asyncio event is not for a worker thread to set.
            self._look()
        await self._hold.run_while(on=hold)

    def give_back(self, owner: str | None) -> bool:
        """Let the firmware run the fans on its own curve again; blocks briefly.

        A plugin that drives the fans now keeps them as it set them: only ORIGAMI's record goes.
        Returns whether the firmware got them back, so the power keeper is to look at the limits.
        """
        journal = self._context.journal
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
        self._hold.cancel()

    def _write(self, points: tuple[int, ...]) -> None:
        """Send the curve to the fans, the journal remembering first; blocks briefly."""
        journal = self._context.journal
        if not journal.recorded("fans", "curve"):
            # The fans ran the firmware's own curve before ORIGAMI, not a value.
            journal.record("fans", "curve", None)
        write_curve(self._context.root, points)
        self._written = points
        log.info("Fan curve written: %s", "/".join(map(str, points)))

    async def _hold_curve(self) -> None:
        """Switch the curve on again whenever something switches it off: a platform profile, say."""
        root = self._context.root
        while True:
            await asyncio.sleep(POLL_SECONDS)
            curve = self._curve
            if curve is None or not curve.enabled or await asyncio.to_thread(curve_on, root):
                continue
            try:
                await asyncio.to_thread(write_curve, root, curve.points)
                log.info("Fan curve switched on again")
            except OSError as error:
                log.warning("Fan curve not switched on again: %s", error)
