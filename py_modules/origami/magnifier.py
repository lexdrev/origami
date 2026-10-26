# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""Steam's screen magnifier, kept on until switched off.

Steam magnifies the screen only while Steam + L1 is held: it sets STEAM_SCREEN_MAGNIFICATION on
gamescope's root window to 1.5x and back to 1x on release (measured on the console 2026-10-27).
ORIGAMI sets the same property itself, so one press switches the magnifier on and the next off.
"""

from pathlib import Path

from origami.gamescope import read_cardinal, write_cardinal

ATOM = "STEAM_SCREEN_MAGNIFICATION"
UNMAGNIFIED = 65535
"""1x; the property counts in 65535ths."""
MAGNIFIED = 98302
"""1.5x, what Steam sets."""


async def toggle_magnifier(root: Path) -> bool:
    """Switch the magnifier on or off; return whether it is on now.

    Raise CommandError or TimeoutError when gamescope cannot be reached.
    """
    on = await read_cardinal(root, ATOM) in (None, UNMAGNIFIED)
    await write_cardinal(root, ATOM, MAGNIFIED if on else UNMAGNIFIED)
    return on
