# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""Screen saturation, written to gamescope the way vibrantDeck does it.

Steam's own Color Vibrance does not reach gamescope on this console: whatever Steam shows, the
root-window property gamescope reads stays at 0.5. So ORIGAMI sets that property itself on
gamescope's first Xwayland display, where Steam runs: GAMESCOPE_COLOR_SDR_GAMUT_WIDENESS, a float
from 0 to 1 stored as a 32-bit CARDINAL, 0.5 being sRGB. ORIGAMI shows it as 0-200%.
"""

import asyncio
import os
from array import array
from pathlib import Path

from origami.proc import CommandError, run

ATOM = "GAMESCOPE_COLOR_SDR_GAMUT_WIDENESS"
DISPLAY = ":0"
X_SOCKET = Path("tmp/.X11-unix/X0")
"""Socket of that display; it belongs to the session user, who may talk to it."""
MAX_PERCENT = 200
TIMEOUT_SECONDS = 5


# The float's bits read as an unsigned 32-bit integer, the way gamescope reads the property.
# (array, not struct: Decky's Python does not bundle the struct module.)
def to_cardinal(percent: int) -> int:
    return array("I", array("f", [percent / MAX_PERCENT]).tobytes())[0]


def from_cardinal(value: int) -> int:
    return round(array("f", array("I", [value]).tobytes())[0] * MAX_PERCENT)


def _display_owner(root: Path) -> tuple[int, int] | None:
    try:
        socket = (root / X_SOCKET).stat()
    except FileNotFoundError:
        return None
    return socket.st_uid, socket.st_gid


async def _xprop(root: Path, *args: str) -> str:
    owner = await asyncio.to_thread(_display_owner, root)
    if owner is None:
        raise CommandError("gamescope's display is not there")
    # As the user who owns the display: root may not be let in.
    user = None if owner[0] == os.geteuid() else owner
    async with asyncio.timeout(TIMEOUT_SECONDS):
        return await run("xprop", "-display", DISPLAY, "-root", *args, user=user)


async def read_saturation(root: Path) -> int | None:
    """The saturation gamescope shows now; None when its display or the property is not there."""
    try:
        output = await _xprop(root, ATOM)
    except CommandError, TimeoutError:
        return None
    # "GAMESCOPE_COLOR_SDR_GAMUT_WIDENESS(CARDINAL) = 1056964608", or "...: not found."
    _, found, value = output.partition("=")
    return from_cardinal(int(value.strip())) if found else None


async def write_saturation(root: Path, percent: int) -> None:
    """Set the saturation; raise CommandError or TimeoutError when gamescope cannot be reached."""
    await _xprop(root, "-f", ATOM, "32c", "-set", ATOM, str(to_cardinal(percent)))
