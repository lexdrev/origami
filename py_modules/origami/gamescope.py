# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Properties of the windows of gamescope's first Xwayland display, where Steam runs.

gamescope reads its settings from the root window's, and Steam writes them for its own
features; the other windows tell gamescope with theirs how to show them. ORIGAMI reads and
writes them with xprop as the user who owns the display: root may not be let in.
"""

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import aclosing
from pathlib import Path

from origami.proc import CommandError, follow, run, run_blocking

DISPLAY = ":0"
PROC = Path("proc")
COMPOSITOR_NAMES = frozenset({"gamescope", "gamescope-wl"})
"""gamescope's main thread is named gamescope-wl on Bazzite 45 and SteamOS 3.9 (2026-11-05); the
session's scripts beside it (gamescope-session-plus) are not the compositor."""
X_SOCKET = Path("tmp/.X11-unix/X0")
"""Socket of that display; it belongs to the session user, who may talk to it."""
TIMEOUT_SECONDS = 5


def gamescope_running(root: Path) -> bool:
    """Whether gamescope runs, as in game mode; in desktop mode display :0 is the desktop's."""
    try:
        entries = list((root / PROC).iterdir())
    except OSError:
        return False
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            name = (entry / "comm").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if name in COMPOSITOR_NAMES:
            return True
    return False


def _display_owner(root: Path) -> tuple[int, int] | None:
    try:
        socket = (root / X_SOCKET).stat()
    except FileNotFoundError:
        return None
    return socket.st_uid, socket.st_gid


def _as_owner(root: Path, *command: str) -> tuple[tuple[str, ...], tuple[int, int] | None]:
    """The command for gamescope's display and the user to run it as."""
    owner = _display_owner(root)
    if owner is None:
        raise CommandError("gamescope's display is not there")
    user = None if owner[0] == os.geteuid() else owner
    return command, user


def _xprop_command(root: Path, *args: str) -> tuple[tuple[str, ...], tuple[int, int] | None]:
    """The xprop command for the root window and the user to run it as."""
    return _as_owner(root, "xprop", "-display", DISPLAY, "-root", *args)


async def _xprop(root: Path, *args: str) -> str:
    command, user = await asyncio.to_thread(_xprop_command, root, *args)
    async with asyncio.timeout(TIMEOUT_SECONDS):
        return await run(*command, user=user)


async def read_cardinal(root: Path, atom: str) -> int | None:
    """A 32-bit CARDINAL property, None while it is not set.

    Raise CommandError or TimeoutError when the display cannot be reached: that is not the same
    as a property nobody set.
    """
    output = await _xprop(root, atom)
    # "ATOM(CARDINAL) = 1056964608", or "ATOM:  not found."
    _, found, value = output.partition("=")
    return int(value.strip()) if found else None


async def write_cardinal(root: Path, atom: str, value: int) -> None:
    """Set a 32-bit CARDINAL property; raise CommandError or TimeoutError on failure."""
    await _xprop(root, *_set_cardinal(atom, value))


def write_cardinal_blocking(root: Path, atom: str, value: int) -> None:
    """write_cardinal() for code that cannot await."""
    command, user = _xprop_command(root, *_set_cardinal(atom, value))
    run_blocking(*command, timeout=TIMEOUT_SECONDS, user=user)


def _set_cardinal(atom: str, value: int) -> tuple[str, ...]:
    return ("-f", atom, "32c", "-set", atom, str(value))


async def list_windows(root: Path) -> str:
    """The display's top windows as xwininfo lists them, one a line with its id, name and class."""
    command, user = await asyncio.to_thread(
        _as_owner, root, "xwininfo", "-display", DISPLAY, "-root", "-children"
    )
    async with asyncio.timeout(TIMEOUT_SECONDS):
        return await run(*command, user=user)


def _window_command(
    root: Path, window: int, *args: str
) -> tuple[tuple[str, ...], tuple[int, int] | None]:
    return _as_owner(root, "xprop", "-display", DISPLAY, "-id", hex(window), *args)


async def read_window(root: Path, window: int, *atoms: str) -> str:
    """xprop's lines for these properties of a window, "ATOM(CARDINAL) = 1" for one that is set."""
    command, user = await asyncio.to_thread(_window_command, root, window, *atoms)
    async with asyncio.timeout(TIMEOUT_SECONDS):
        return await run(*command, user=user)


async def read_root(root: Path, *atoms: str) -> str:
    """xprop's lines for these properties of the root window."""
    return await _xprop(root, *atoms)


async def write_window_cardinal(root: Path, window: int, atom: str, value: int) -> None:
    """Set a 32-bit CARDINAL property of a window; raise CommandError or TimeoutError on failure."""
    command, user = await asyncio.to_thread(
        _window_command, root, window, *_set_cardinal(atom, value)
    )
    async with asyncio.timeout(TIMEOUT_SECONDS):
        await run(*command, user=user)


async def spy_window(root: Path, window: int, *atoms: str) -> AsyncGenerator[str]:
    """xprop's lines for these properties of a window: as they are now, then on every change.

    A property written again with the same value is a change too. It ends when xprop does, which
    is not promised when the window goes: the caller looks whether the window is still there.
    """
    command, user = await asyncio.to_thread(_window_command, root, window, "-spy", *atoms)
    async with aclosing(follow(*command, user=user)) as lines:
        async for line in lines:
            yield line
