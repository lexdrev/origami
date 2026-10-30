# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""The buttons ORIGAMI drives on the Gamepad screen: the Armoury Crate button and QAM assist.

Their presses are read from the controller (origami.buttons) while a setting needs them.
"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import aclosing

from origami.blocks import Context, Emit
from origami.buttons import Button, ButtonAction, button_presses, layout_for
from origami.inputplumber import Chord, press_chord
from origami.magnifier import Magnifier
from origami.proc import CommandError
from origami.settings import Settings
from origami.tasks import BackgroundTask

log = logging.getLogger(__name__)

QAM_PRESSED = "qam_pressed"
"""Event sent to the frontend on every press of the quick access button while QAM assist is on."""
BUTTON_ACTION = "button_action"
"""Event sent to the frontend with the action of a button ORIGAMI drives, on every press of it."""

CHORDS = {
    ButtonAction.SCREENSHOT: Chord.SCREENSHOT,
    ButtonAction.KEYBOARD: Chord.KEYBOARD,
    ButtonAction.L5: Chord.L5,
}
"""Actions that are buttons Steam knows, which ORIGAMI presses through InputPlumber."""


def driven_buttons(settings: Settings) -> frozenset[Button]:
    """The buttons whose presses ORIGAMI needs with these settings."""
    driven = {
        Button.QUICK_ACCESS: settings.qam_assist is True,
        Button.ARMOURY_CRATE: settings.armoury_crate not in {None, ButtonAction.NONE},
        Button.ARMOURY_CRATE_HOLD: settings.armoury_crate_hold not in {None, ButtonAction.NONE},
    }
    return frozenset(button for button, needed in driven.items() if needed)


class ButtonsBlock:
    """Reads the presses the settings need and carries out their actions.

    The backend does what it can itself (Steam's chords, the magnifier) and has the frontend do
    the rest in Steam's interface through events. `board` names the console's board, or None.
    """

    def __init__(self, context: Context, *, emit: Emit, board: Callable[[], str | None]) -> None:
        self._root = context.root
        self._emit = emit
        self._board = board
        self._magnifier = Magnifier(context.root)
        self._settings = Settings()
        self._read: frozenset[Button] = frozenset()
        self._reader = BackgroundTask("origami-buttons", self._forward)

    async def follow(self, settings: Settings) -> None:
        self._settings = settings
        buttons = driven_buttons(settings)
        if buttons != self._read:
            # The reader opens only the interfaces its buttons come from.
            await self._reader.stop()
            self._read = buttons
        await self._reader.run_while(on=bool(buttons))

    def stop(self) -> None:
        """Stop reading, and switch the magnifier off, giving the game its right stick back."""
        self._reader.cancel()
        try:
            self._magnifier.close()
        except (CommandError, TimeoutError) as error:
            log.warning("Magnifier not switched off: %s", error)

    async def _forward(self) -> None:
        presses = button_presses(self._root, self._read, layout=layout_for(self._board()))
        async with aclosing(presses):
            async for button in presses:
                match button:
                    case Button.QUICK_ACCESS:
                        # Steam misses some presses while a game runs (B16). The frontend sees
                        # whether Steam registered this one and opens the menu itself if not.
                        await self._emit(QAM_PRESSED)
                    case Button.ARMOURY_CRATE:
                        await self._act(self._settings.armoury_crate or ButtonAction.NONE)
                    case Button.ARMOURY_CRATE_HOLD:
                        await self._act(self._settings.armoury_crate_hold or ButtonAction.NONE)

    async def _act(self, action: ButtonAction) -> None:
        """Do what the backend can do itself; have the frontend do the rest in Steam's interface."""
        chord = CHORDS.get(action)
        try:
            if chord is not None:
                await asyncio.to_thread(press_chord, self._root, chord)
            elif action is ButtonAction.MAGNIFIER:
                await asyncio.to_thread(self._magnifier.toggle)
            elif action is not ButtonAction.NONE:
                await self._emit(BUTTON_ACTION, action.value)
        except (CommandError, TimeoutError, ValueError) as error:
            log.warning("%s not done: %s", action.value, error)
