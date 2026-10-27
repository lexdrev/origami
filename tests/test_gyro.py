# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import stat

import pytest

from origami.gyro import (
    OVERRIDE,
    STOCK,
    GyroState,
    read_gyro_state,
    remove_fix,
    write_fix,
)

from fakes import FakeRoot

# The IMU part of InputPlumber 0.83.0's device file for the ROG Xbox Ally (X), as on the console.
STOCK_TEXT = """name: ASUS ROG Xbox Ally
matches:
  - dmi_data:
      board_name: RC73XA
source_devices:
  - group: imu
    iio:
      name: bmi323-imu
    config:
      imu:
        mount_matrix:
          # TODO: Verify on actual hardware
          x: [1, 0, 0]
          y: [0, 0, 1]
          z: [0, 1, 0]
"""


@pytest.fixture
def stock(fake_root: FakeRoot) -> FakeRoot:
    path = fake_root.path / STOCK
    path.parent.mkdir(parents=True)
    path.write_text(STOCK_TEXT, encoding="utf-8")
    (fake_root.path / OVERRIDE).parent.mkdir(parents=True)
    return fake_root


def test_the_stock_axes_are_wrong_on_the_xbox_ally(stock: FakeRoot) -> None:
    assert read_gyro_state(stock.path, "RC73XA") is GyroState.WRONG
    assert read_gyro_state(stock.path, "RC73YA") is GyroState.WRONG


@pytest.mark.parametrize("board", ["RC74XA", "RC72LA", None])
def test_other_devices_are_left_alone(stock: FakeRoot, board: str | None) -> None:
    assert read_gyro_state(stock.path, board) is GyroState.UNAVAILABLE


def test_nothing_to_fix_without_inputplumber(fake_root: FakeRoot) -> None:
    assert read_gyro_state(fake_root.path, "RC73XA") is GyroState.UNAVAILABLE


def test_the_fix_is_the_stock_file_with_the_yaw_row_turned(stock: FakeRoot) -> None:
    write_fix(stock.path)

    path = stock.path / OVERRIDE
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("# Written by ORIGAMI")
    assert lines[1:] == STOCK_TEXT.replace("z: [0, 1, 0]", "z: [0, -1, 0]").splitlines()
    assert stat.S_IMODE(path.stat().st_mode) == 0o644
    assert read_gyro_state(stock.path, "RC73XA") is GyroState.FIXED


def test_a_fix_made_from_an_older_stock_file_is_outdated(stock: FakeRoot) -> None:
    write_fix(stock.path)
    (stock.path / STOCK).write_text(STOCK_TEXT + "  - group: led\n", encoding="utf-8")

    assert read_gyro_state(stock.path, "RC73XA") is GyroState.OUTDATED


def test_another_programs_file_is_never_touched(stock: FakeRoot) -> None:
    foreign = stock.path / OVERRIDE
    foreign.write_text(STOCK_TEXT, encoding="utf-8")

    assert read_gyro_state(stock.path, "RC73XA") is GyroState.FOREIGN
    assert remove_fix(stock.path) is False
    assert foreign.exists()


def test_removing_the_fix_gives_back_the_stock_axes(stock: FakeRoot) -> None:
    write_fix(stock.path)

    assert remove_fix(stock.path) is True
    assert not (stock.path / OVERRIDE).exists()
    assert read_gyro_state(stock.path, "RC73XA") is GyroState.WRONG
    assert remove_fix(stock.path) is False


def test_a_stock_file_with_the_right_axes_needs_no_fix(stock: FakeRoot) -> None:
    (stock.path / STOCK).write_text(STOCK_TEXT.replace("[0, 1, 0]", "[0, -1, 0]"), encoding="utf-8")

    assert read_gyro_state(stock.path, "RC73XA") is GyroState.FIXED_IN_SYSTEM


def test_a_stock_file_origami_does_not_know_is_left_alone(stock: FakeRoot) -> None:
    (stock.path / STOCK).write_text(
        STOCK_TEXT.replace("z: [0, 1, 0]", "z: [1, 0, 0]"), encoding="utf-8"
    )

    assert read_gyro_state(stock.path, "RC73XA") is GyroState.UNAVAILABLE
