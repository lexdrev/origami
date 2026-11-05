# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Display & Light tile: gamescope's saturation and the lighting of the stick rings."""

import asyncio
import logging
from collections.abc import Callable

from origami.blocks import Context
from origami.gamescope import gamescope_running
from origami.lighting import CONTROLLER_LIGHTING, Lighting, apply_lighting
from origami.proc import CommandError
from origami.saturation import (
    MAX_PERCENT,
    SRGB_PERCENT,
    read_saturation,
    write_saturation,
    write_saturation_blocking,
)
from origami.settings import Settings

log = logging.getLogger(__name__)


class DisplayBlock:
    """Sends the saturation and the lighting; the rings share the controller with the gamepad.

    Both blocks talk to the controller's MCU, and two reports at once could interleave, so each
    takes `controller_lock` around what it sends to it.
    """

    def __init__(
        self,
        context: Context,
        controller_lock: asyncio.Lock,
        *,
        saturation_top: Callable[[], int] = lambda: MAX_PERCENT,
    ) -> None:
        self._context = context
        self._controller_lock = controller_lock
        self._top = saturation_top
        """The top of the saturation scale on this system: 200% on Bazzite, 100% on SteamOS."""

    async def saturation(self) -> int | None:
        """The saturation gamescope shows now, ORIGAMI's or not; None without gamescope."""
        try:
            percent = await read_saturation(self._context.root, top=self._top())
        except CommandError, TimeoutError:
            return None
        return SRGB_PERCENT if percent is None else percent

    async def send_saturation(self, percent: int) -> None:
        owner = (await self._context.conflicts()).saturation
        if owner is not None:
            raise RuntimeError(f"{owner} sets the screen colour, so ORIGAMI leaves it alone")
        journal, root = self._context.journal, self._context.root
        if not journal.recorded("display", "saturation"):
            # Raises when gamescope cannot be read: nothing is written then, not even the original.
            original = await read_saturation(root, top=self._top())
            await asyncio.to_thread(journal.record, "display", "saturation", original)
        await write_saturation(root, percent, top=self._top())

    async def restore_saturation(self, settings: Settings, *, last_try: bool = True) -> bool:
        """Send the saved saturation again; False when gamescope could not be reached yet.

        Right after Steam's session starts, xprop may find no display or be refused at first
        ("Authorization required", 2026-11-02 on Bazzite, 2026-11-04 on SteamOS), so the caller
        tries again. Failures are logged on the last try, and at once when another try cannot help.
        """
        if settings.saturation is None:
            return True
        if not await asyncio.to_thread(gamescope_running, self._context.root):
            # Steam in desktop mode loads ORIGAMI too; the saturation waits for game mode.
            return True
        try:
            await self.send_saturation(settings.saturation)
        except (CommandError, TimeoutError) as error:
            if last_try:
                log.warning("Saturation not restored: %s", error)
            return False
        except (OSError, RuntimeError) as error:
            log.warning("Saturation not restored: %s", error)
        return True

    async def give_back_saturation(self, owner: str | None) -> None:
        """Gamescope's saturation as it was before ORIGAMI, unless a plugin sets it now."""
        journal = self._context.journal
        if not journal.recorded("display", "saturation"):
            return
        if owner is None:
            try:
                await write_saturation(
                    self._context.root, self._saturation_before(), top=self._top()
                )
            except (CommandError, OSError, TimeoutError) as error:
                log.warning("Saturation not given back: %s", error)
                return
        await asyncio.to_thread(journal.forget, "display", "saturation")

    def give_back_saturation_now(self, owner: str | None) -> None:
        """give_back_saturation() for uninstall, which cannot await."""
        journal = self._context.journal
        if not journal.recorded("display", "saturation"):
            return
        if owner is None:
            try:
                write_saturation_blocking(
                    self._context.root, self._saturation_before(), top=self._top()
                )
            except (CommandError, OSError, TimeoutError) as error:
                log.warning("Saturation not given back: %s", error)
                return
        journal.forget("display", "saturation")

    async def send_lighting(self, lighting: Lighting) -> None:
        owner = (await self._context.conflicts()).lighting
        if owner is not None:
            raise RuntimeError(f"{owner} drives the stick lighting, so ORIGAMI leaves it alone")
        async with self._controller_lock:
            # The controller cannot report its lighting, so the original is its own animation.
            await asyncio.to_thread(self._context.journal.record, "lighting", "rings", None)
            await asyncio.to_thread(apply_lighting, self._context.root, lighting)

    async def restore_lighting(self, settings: Settings) -> None:
        """Send the saved lighting again, at start and after sleep; failures are only logged."""
        if settings.lighting is None:
            return
        try:
            await self.send_lighting(settings.lighting)
        except (OSError, RuntimeError) as error:
            log.warning("Lighting not restored: %s", error)

    def give_back_lighting(self, owner: str | None) -> None:
        """The rings' own animation, as before ORIGAMI; blocks briefly.

        A plugin that drives them now keeps them as it set them: only ORIGAMI's record goes.
        """
        journal = self._context.journal
        if not journal.recorded("lighting", "rings"):
            return
        try:
            if owner is None:
                apply_lighting(self._context.root, CONTROLLER_LIGHTING)
            journal.forget("lighting", "rings")
        except OSError as error:
            log.warning("Lighting not given back: %s", error)

    def _saturation_before(self) -> int:
        """The saturation before ORIGAMI; nobody had set it (None) while gamescope showed sRGB."""
        original = self._context.journal.original("display", "saturation")
        if isinstance(original, int) and not isinstance(original, bool):
            return original
        return SRGB_PERCENT
