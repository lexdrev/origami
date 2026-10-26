# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from origami.telemetry import (
    FanTelemetry,
    GamepadTelemetry,
    PowerTelemetry,
    Telemetry,
    read_telemetry,
)

from fakes import FakeRoot


def test_ally_x(ally_x: FakeRoot) -> None:
    assert read_telemetry(ally_x.path) == Telemetry(
        power=PowerTelemetry(tdp_limit_w=17, package_power_w=16.9, cpu_boost=False),
        fans=FanTelemetry(speeds_rpm=[4600, 4700], cpu_temp_c=61.625, gpu_temp_c=61.0),
        gamepad=GamepadTelemetry(vibration_pct=(50, 50)),
    )


def test_other_hardware_reads_as_unknown(fake_root: FakeRoot) -> None:
    assert read_telemetry(fake_root.path) == Telemetry(
        power=PowerTelemetry(tdp_limit_w=None, package_power_w=None, cpu_boost=None),
        fans=FanTelemetry(speeds_rpm=[], cpu_temp_c=None, gpu_temp_c=None),
        gamepad=GamepadTelemetry(vibration_pct=None),
    )


def test_unreadable_fan_is_skipped(ally_x: FakeRoot) -> None:
    ally_x.write("sys/class/hwmon/hwmon6/fan2_input", "")

    assert read_telemetry(ally_x.path).fans.speeds_rpm == [4600]


@pytest.mark.parametrize("value", ["50", "a b", "50 50 50", ""])
def test_unexpected_vibration_value(ally_x: FakeRoot, value: str) -> None:
    ally_x.write(
        "sys/module/hid_asus_ally/drivers/hid:asus_rog_ally/0003:0B05:1B4C.0004/vibration_intensity",
        value,
    )

    assert read_telemetry(ally_x.path).gamepad.vibration_pct is None
