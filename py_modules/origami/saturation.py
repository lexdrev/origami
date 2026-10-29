# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Screen saturation, written to gamescope directly.

Steam's own Color Vibrance does not reach gamescope on this console: whatever Steam shows, the
root-window property gamescope reads stays at 0.5. So ORIGAMI sets that property itself:
GAMESCOPE_COLOR_SDR_GAMUT_WIDENESS, a float from 0 to 1 stored as a 32-bit CARDINAL, 0.5 being
sRGB. ORIGAMI shows it as 0-200%.
"""

from array import array
from pathlib import Path

from origami.gamescope import read_cardinal, write_cardinal

ATOM = "GAMESCOPE_COLOR_SDR_GAMUT_WIDENESS"
MAX_PERCENT = 200
SRGB_PERCENT = 100
"""What gamescope shows while nobody has set the property."""


# The float's bits read as an unsigned 32-bit integer, the way gamescope reads the property.
# (array, not struct: Decky's Python does not bundle the struct module.)
def to_cardinal(percent: int) -> int:
    return array("I", array("f", [percent / MAX_PERCENT]).tobytes())[0]


def from_cardinal(value: int) -> int:
    return round(array("f", array("I", [value]).tobytes())[0] * MAX_PERCENT)


async def read_saturation(root: Path) -> int | None:
    """The saturation set now, None while nobody has set it (gamescope then shows sRGB).

    Raise CommandError or TimeoutError when gamescope cannot be reached.
    """
    value = await read_cardinal(root, ATOM)
    return None if value is None else from_cardinal(value)


async def write_saturation(root: Path, percent: int) -> None:
    """Set the saturation; raise CommandError or TimeoutError when gamescope cannot be reached."""
    await write_cardinal(root, ATOM, to_cardinal(percent))
