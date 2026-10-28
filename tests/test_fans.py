# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

import pytest

from origami.fans import BALANCE, FanCurve, curve_on, give_back, write_curve

from fakes import FakeRoot


def curve_device(root: FakeRoot) -> Path:
    """The firmware's curve device as after boot: both fans on the firmware's own curve."""
    return root.hwmon(8, "asus_custom_fan_curve", pwm1_enable=2, pwm2_enable=2)


def read(device: Path, name: str) -> int:
    return int((device / name).read_text(encoding="utf-8"))


def test_the_curve_goes_to_both_fans_and_on_with_full_speed_at_100(fake_root: FakeRoot) -> None:
    device = curve_device(fake_root)

    write_curve(fake_root.path, (0, 10, 25, 40, 55, 75, 100))

    for fan in (1, 2):
        temps = [read(device, f"pwm{fan}_auto_point{index}_temp") for index in range(1, 9)]
        speeds = [read(device, f"pwm{fan}_auto_point{index}_pwm") for index in range(1, 9)]
        assert temps == [30, 40, 50, 60, 70, 80, 90, 100]
        assert speeds == [0, 26, 64, 102, 140, 191, 255, 255]
        assert read(device, f"pwm{fan}_enable") == 1
    assert curve_on(fake_root.path)


def test_a_profile_written_switches_the_curve_off_and_giving_back_hands_over(
    fake_root: FakeRoot,
) -> None:
    device = curve_device(fake_root)
    write_curve(fake_root.path, BALANCE)

    # asus-wmi switches custom curves off as a platform profile is written.
    fake_root.write(f"sys/class/hwmon/{device.name}/pwm2_enable", 2)
    assert not curve_on(fake_root.path)

    give_back(fake_root.path)
    assert [read(device, "pwm1_enable"), read(device, "pwm2_enable")] == [2, 2]


def test_without_the_curve_device_nothing_is_written(fake_root: FakeRoot) -> None:
    with pytest.raises(OSError, match="asus_custom_fan_curve"):
        write_curve(fake_root.path, BALANCE)
    assert not curve_on(fake_root.path)
    give_back(fake_root.path)


@pytest.mark.parametrize(
    ("points", "message"),
    [
        ([0, 10, 25, 40, 55, 75], "7 points"),
        ([0, 10, 25, 40, 55, 75, 101], "percentage"),
        ([0, 10, 25, 40, 55, 75, True], "percentage"),
        ([0, 20, 10, 40, 55, 75, 100], "fall"),
        ([0, 10, 25, 40, 45, 45, 45], "at least at 50%"),
    ],
)
def test_curves_that_fall_or_run_hot_are_refused(points: list[object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        FanCurve.from_json({"enabled": True, "points": points})


def test_a_curve_switched_off_keeps_its_points() -> None:
    curve = FanCurve.from_json({"enabled": False, "points": [20, 30, 45, 60, 75, 90, 100]})

    assert curve == FanCurve(enabled=False, points=(20, 30, 45, 60, 75, 90, 100))
    assert FanCurve.from_json(curve.to_json()) == curve
    assert FanCurve.from_json({}) == FanCurve(enabled=True, points=BALANCE)
