# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from pathlib import Path

from origami.sysfs import read_text

DMI = Path("sys/class/dmi/id")

# Matched by board name: the X20 reports sys_vendor "ASUS" instead of "ASUSTeK COMPUTER INC.".
MODELS = {
    "RC73XA": "ROG Xbox Ally X",
    "RC74XA": "ROG Xbox Ally X20",
}


@dataclass(frozen=True, slots=True)
class Device:
    board: str | None
    product: str | None
    model: str | None
    """Known model name; None on hardware ORIGAMI does not support."""


def read_device(root: Path) -> Device:
    board = read_text(root / DMI / "board_name")
    return Device(
        board=board,
        product=read_text(root / DMI / "product_name"),
        model=MODELS.get(board) if board else None,
    )
