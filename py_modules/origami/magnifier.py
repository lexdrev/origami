# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""Steam's screen magnifier, kept on until switched off and moved with the right stick.

Steam magnifies the screen only while Steam + L1 is held: it sets STEAM_SCREEN_MAGNIFICATION on
gamescope's root window to 1.5x and back to 1x on release (measured on the console 2026-10-27).
gamescope magnifies around the mouse pointer, which Steam moves with the right stick meanwhile; a
game gets that motion too and turns its camera (watched 2026-10-28). ORIGAMI sets the property
itself, so one press switches the magnifier on and the next off, and while it is on, the built-in
controller's InputPlumber profile has the right stick move the mouse. Without that, the magnifier
stays where gamescope parks the hidden pointer: in a corner.

The calls block: the plugin runs them in a thread, and switches the magnifier off as it unloads,
when nothing can be awaited.
"""

import threading
from pathlib import Path

from origami.gamescope import write_cardinal_blocking
from origami.inputplumber import (
    Profile,
    builtin_device,
    current_profile,
    load_profile,
    load_profile_text,
    profile_path,
)

ATOM = "STEAM_SCREEN_MAGNIFICATION"
UNMAGNIFIED = 65535
"""1x; the property counts in 65535ths."""
MAGNIFIED = 98302
"""1.5x, what Steam sets."""
STICK_SPEED = 2000
"""Pointer pixels a second at full tilt; Steam's 4500 (230 px in 50 ms) is too fast to aim."""
STICK_AS_MOUSE = f"""- name: Right stick as the mouse (ORIGAMI magnifier)
  source_event:
    gamepad:
      axis:
        name: RightStick
  target_events:
  - mouse:
      motion:
        speed_pps: {STICK_SPEED}
"""


def with_stick_as_mouse(profile: str) -> str:
    """The profile with the right stick moving the mouse.

    InputPlumber writes the mapping last, as its DeviceProfile declares it, and `[]` when it is
    empty. Raise ValueError for a profile laid out otherwise.
    """
    text = profile.rstrip("\n")
    if text.endswith("\nmapping: []"):
        text = text.removesuffix(" []")
    keys = [line for line in text.splitlines() if line[:1].isalpha()]
    if not keys or keys[-1] != "mapping:":
        raise ValueError("InputPlumber's profile does not end with its mapping")
    return f"{text}\n{STICK_AS_MOUSE}"


class Magnifier:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._lock = threading.Lock()
        self._on = False
        self._before: Profile | None = None
        """The profile from before the right stick became the mouse; None while it is not."""

    def toggle(self) -> bool:
        """Switch the magnifier on or off; return whether it is on now.

        Raise CommandError or TimeoutError when gamescope or InputPlumber cannot be reached, and
        ValueError for a profile the stick cannot be added to. The screen is magnified first:
        without gamescope nothing changes, and a press switches off whatever was switched on.
        """
        with self._lock:
            if self._on:
                self._switch_off()
                return False
            write_cardinal_blocking(self._root, ATOM, MAGNIFIED)
            self._on = True
            before = current_profile(builtin_device(self._root))
            load_profile_text(before.device, with_stick_as_mouse(before.text))
            self._before = before
            return True

    def close(self) -> None:
        """Switch ORIGAMI's magnifier off, if it is on."""
        with self._lock:
            if self._on:
                self._switch_off()

    def _switch_off(self) -> None:
        before, self._before, self._on = self._before, None, False
        try:
            # A profile loaded from text has no path. One with a path was loaded meanwhile, as
            # OpenGamepadUI does for a game that starts, and stays.
            if before is not None and not profile_path(before.device):
                load_profile(before)
        finally:
            write_cardinal_blocking(self._root, ATOM, UNMAGNIFIED)
