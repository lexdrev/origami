# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""Properties of the root window of gamescope's first Xwayland display, where Steam runs.

gamescope reads its settings from them, and Steam writes them for its own features. ORIGAMI
reads and writes them with xprop as the user who owns the display: root may not be let in.
"""

import asyncio
import os
from pathlib import Path

from origami.proc import CommandError, run

DISPLAY = ":0"
X_SOCKET = Path("tmp/.X11-unix/X0")
"""Socket of that display; it belongs to the session user, who may talk to it."""
TIMEOUT_SECONDS = 5


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
    user = None if owner[0] == os.geteuid() else owner
    async with asyncio.timeout(TIMEOUT_SECONDS):
        return await run("xprop", "-display", DISPLAY, "-root", *args, user=user)


async def read_cardinal(root: Path, atom: str) -> int | None:
    """A 32-bit CARDINAL property; None when the display or the property is not there."""
    try:
        output = await _xprop(root, atom)
    except CommandError, TimeoutError:
        return None
    # "ATOM(CARDINAL) = 1056964608", or "ATOM:  not found."
    _, found, value = output.partition("=")
    return int(value.strip()) if found else None


async def write_cardinal(root: Path, atom: str, value: int) -> None:
    """Set a 32-bit CARDINAL property; raise CommandError or TimeoutError on failure."""
    await _xprop(root, "-f", atom, "32c", "-set", atom, str(value))
