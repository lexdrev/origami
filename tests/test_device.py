# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from origami.device import Device, read_device

from fakes import FakeRoot


def test_ally_x(ally_x: FakeRoot) -> None:
    assert read_device(ally_x.path) == Device(
        board="RC73XA", product="ROG Xbox Ally X RC73XA_RC73XA", model="ROG Xbox Ally X"
    )


@pytest.mark.parametrize(
    ("board", "model"),
    [("RC74XA", "ROG Xbox Ally X20"), ("RC72LA", None), ("Jupiter", None)],
)
def test_model_is_detected_by_board(fake_root: FakeRoot, board: str, model: str | None) -> None:
    fake_root.write("sys/class/dmi/id/board_name", board)

    assert read_device(fake_root.path).model == model


def test_no_dmi(fake_root: FakeRoot) -> None:
    assert read_device(fake_root.path) == Device(board=None, product=None, model=None)
