# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from origami.telemetry import (
    BatteryTelemetry,
    FanTelemetry,
    GamepadTelemetry,
    PowerTelemetry,
    Telemetry,
    read_telemetry,
)

from fakes import FakeRoot


def test_ally_x(ally_x: FakeRoot) -> None:
    assert read_telemetry(ally_x.path) == Telemetry(
        power=PowerTelemetry(
            tdp_limit_w=17, package_power_w=16.9, cpu_boost=False, on_battery=False, battery=None
        ),
        fans=FanTelemetry(speeds_rpm=[4600, 4700], cpu_temp_c=61.625, gpu_temp_c=61.0),
        gamepad=GamepadTelemetry(vibration_pct=(50, 50)),
    )


def test_other_hardware_reads_as_unknown(fake_root: FakeRoot) -> None:
    assert read_telemetry(fake_root.path) == Telemetry(
        power=PowerTelemetry(
            tdp_limit_w=None, package_power_w=None, cpu_boost=None, on_battery=False, battery=None
        ),
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


def test_the_battery(powered: FakeRoot) -> None:
    power = read_telemetry(powered.path).power

    assert power.on_battery is True
    # 40 Wh at 20 W lasts two hours; 74.3 Wh of the design's 80 is 93% of its capacity.
    assert power.battery == BatteryTelemetry(
        percent=54, charging=False, minutes_left=120, capacity_pct=93
    )


def test_a_charging_battery_has_no_time_left(powered: FakeRoot) -> None:
    powered.write("sys/class/power_supply/AC0/online", 1)
    powered.write("sys/class/power_supply/BAT0/status", "Charging")

    power = read_telemetry(powered.path).power

    assert power.on_battery is False
    assert power.battery is not None
    assert (power.battery.charging, power.battery.minutes_left) == (True, None)
