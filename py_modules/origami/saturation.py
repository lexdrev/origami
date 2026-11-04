# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Screen saturation, written to gamescope directly.

ORIGAMI sets the root-window property gamescope reads, GAMESCOPE_COLOR_SDR_GAMUT_WIDENESS: a float
from 0 to 1 stored as a 32-bit CARDINAL. 100% is what the system shows by itself. On Bazzite that
is 0.5 (Steam's own Color Vibrance does not reach gamescope there), so the scale runs to 200%.
SteamOS sets 1.0 itself, the widest (RC71L owner's report, 2026-11-04), so there 100% is the top
and ORIGAMI can only take some saturation away.
"""

from array import array
from pathlib import Path

from origami.gamescope import read_cardinal, write_cardinal, write_cardinal_blocking

ATOM = "GAMESCOPE_COLOR_SDR_GAMUT_WIDENESS"
MAX_PERCENT = 200
"""The top of the scale where the system keeps 0.5, as Bazzite."""
STEAMOS_MAX_PERCENT = 100
"""The top on SteamOS, which keeps the widest, 1.0, itself."""
SRGB_PERCENT = 100
"""What the system shows by itself, and gamescope while nobody has set the property."""


def max_percent(system_id: str | None) -> int:
    """The top of the scale on a system, by the ID in its os-release."""
    return STEAMOS_MAX_PERCENT if system_id == "steamos" else MAX_PERCENT


# The float's bits read as an unsigned 32-bit integer, the way gamescope reads the property.
# (array, not struct: Decky's Python does not bundle the struct module.)
def to_cardinal(percent: int, top: int = MAX_PERCENT) -> int:
    return array("I", array("f", [min(percent, top) / top]).tobytes())[0]


def from_cardinal(value: int, top: int = MAX_PERCENT) -> int:
    return round(array("f", array("I", [value]).tobytes())[0] * top)


async def read_saturation(root: Path, top: int = MAX_PERCENT) -> int | None:
    """The saturation set now, None while nobody has set it (gamescope then shows sRGB).

    Raise CommandError or TimeoutError when gamescope cannot be reached.
    """
    value = await read_cardinal(root, ATOM)
    return None if value is None else from_cardinal(value, top)


async def write_saturation(root: Path, percent: int, top: int = MAX_PERCENT) -> None:
    """Set the saturation; raise CommandError or TimeoutError when gamescope cannot be reached."""
    await write_cardinal(root, ATOM, to_cardinal(percent, top))


def write_saturation_blocking(root: Path, percent: int, top: int = MAX_PERCENT) -> None:
    """write_saturation() for code that cannot await."""
    write_cardinal_blocking(root, ATOM, to_cardinal(percent, top))
