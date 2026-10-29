# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Axes of the gyroscope as InputPlumber gives them to Steam (BUGS.md, B08).

InputPlumber 0.83 turns the IMU of the ROG Xbox Ally (X) with the row z [0, 1, 0], marked "TODO:
Verify on actual hardware". Steam then sees the yaw mirrored: the camera goes left when the console
turns right, unless "Invert X" is ticked in every layout. The right row is z [0, -1, 0], as the ROG
Ally X has in the same InputPlumber (checked in a game 2026-10-25). InputPlumber takes a device
file in /etc over the one of the same name in /usr/share, and reads it when it starts, so ORIGAMI
writes the stock file with that row there and restarts InputPlumber.
"""

import asyncio
import hashlib
import re
from enum import StrEnum
from pathlib import Path

from origami.fsutil import atomic_write_text
from origami.proc import run

STOCK = Path("usr/share/inputplumber/devices/50-rog_xbox_ally.yaml")
OVERRIDE = Path("etc/inputplumber/devices.d/50-rog_xbox_ally.yaml")
BOARDS = frozenset({"RC73XA", "RC73YA"})
"""The ROG Xbox Ally X and the ROG Xbox Ally, which share that file. The X20 has its own."""
MARK = "# Written by ORIGAMI: the gyroscope's yaw turned the right way (B08). Stock sha256: "
WRONG_Z = re.compile(r"^(\s*)z: \[0, 1, 0\]$", re.MULTILINE)
RIGHT_Z = re.compile(r"^\s*z: \[0, -1, 0\]$", re.MULTILINE)
RESTART_TIMEOUT_SECONDS = 20


class GyroState(StrEnum):
    UNAVAILABLE = "unavailable"
    """Another device, no InputPlumber, or a stock file ORIGAMI does not know."""
    FIXED_IN_SYSTEM = "fixed_in_system"
    FOREIGN = "foreign"
    """Another program's file in /etc sets the axes; ORIGAMI leaves it alone."""
    WRONG = "wrong"
    FIXED = "fixed"
    """ORIGAMI's file, made from the stock file InputPlumber has now."""
    OUTDATED = "outdated"
    """ORIGAMI's file, made from an older stock file: InputPlumber was updated since."""


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def fixed_text(stock: str) -> str:
    """The stock file with the yaw row turned, marked as ORIGAMI's with the stock file's digest."""
    return f"{MARK}{_digest(stock)}\n" + WRONG_Z.sub(r"\1z: [0, -1, 0]", stock, count=1)


def read_gyro_state(root: Path, board: str | None) -> GyroState:
    stock = _read(root / STOCK)
    if board not in BOARDS or stock is None:
        return GyroState.UNAVAILABLE
    override = _read(root / OVERRIDE)
    if override is not None and not override.startswith(MARK):
        return GyroState.FOREIGN
    if RIGHT_Z.search(stock):
        # A file of ORIGAMI's from before is only a stale copy then.
        return GyroState.FIXED_IN_SYSTEM
    if len(WRONG_Z.findall(stock)) != 1:
        return GyroState.UNAVAILABLE
    if override is None:
        return GyroState.WRONG
    return GyroState.FIXED if override == fixed_text(stock) else GyroState.OUTDATED


def write_fix(root: Path) -> None:
    """Write ORIGAMI's file; InputPlumber takes it when it starts next."""
    path = root / OVERRIDE
    atomic_write_text(path, fixed_text((root / STOCK).read_text(encoding="utf-8")))
    # Readable like the other device files, not only by root as the temporary file was made.
    path.chmod(0o644)


def remove_fix(root: Path) -> bool:
    """Remove ORIGAMI's file, never another program's; return whether there was one."""
    path = root / OVERRIDE
    text = _read(path)
    if text is None or not text.startswith(MARK):
        return False
    path.unlink()
    return True


async def restart_inputplumber() -> None:
    """Restart InputPlumber so it reads its device files; the controller is away for a moment."""
    async with asyncio.timeout(RESTART_TIMEOUT_SECONDS):
        await run("systemctl", "restart", "inputplumber")
