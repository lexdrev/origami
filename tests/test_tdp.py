# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from origami.tdp import (
    Limits,
    Range,
    limits_for,
    on_mains,
    platform_profiles,
    read_limits,
    read_ranges,
    reset_to_profile,
    soc_power,
    write_limits,
)

from fakes import FakeRoot

ARMOURY = "sys/class/firmware-attributes/asus-armoury/attributes"
SUPPLIES = "sys/class/power_supply"
# The battery's ranges and the charger's, whose boost starts at 14 (asus-armoury's table).
BATTERY = (Range(7, 35), Range(13, 45), Range(19, 55))
CHARGER = (Range(7, 35), Range(14, 45), Range(19, 55))


def test_the_headroom_is_the_factorys_above_the_tdp() -> None:
    assert limits_for(17, headroom=True, ranges=BATTERY) == Limits(17, 21, 26)
    assert limits_for(35, headroom=True, ranges=BATTERY) == Limits(35, 39, 44)


def test_without_the_headroom_all_three_are_the_tdp_above_the_firmwares_lowest() -> None:
    assert limits_for(20, headroom=False, ranges=BATTERY) == Limits(20, 20, 20)
    assert limits_for(13, headroom=False, ranges=BATTERY) == Limits(13, 13, 19)
    assert limits_for(13, headroom=False, ranges=CHARGER) == Limits(13, 14, 19)


def test_limits_stay_within_what_the_firmware_takes() -> None:
    assert limits_for(50, headroom=True, ranges=BATTERY) == Limits(35, 39, 44)
    assert limits_for(3, headroom=True, ranges=BATTERY) == Limits(7, 13, 19)


def test_limits_and_ranges_are_read_from_asus_armoury(powered: FakeRoot) -> None:
    assert read_limits(powered.path) == Limits(17, 21, 26)
    assert read_ranges(powered.path) == BATTERY


def test_without_asus_armoury_there_are_no_limits(fake_root: FakeRoot) -> None:
    assert read_limits(fake_root.path) is None
    assert read_ranges(fake_root.path) is None


def test_limits_are_written_to_all_three(powered: FakeRoot) -> None:
    write_limits(powered.path, Limits(20, 24, 29))

    assert read_limits(powered.path) == Limits(20, 24, 29)


def test_the_soc_power_comes_from_amdgpu(powered: FakeRoot) -> None:
    assert soc_power(powered.path) == pytest.approx(16.9)


def test_the_charger_or_a_usb_port_online_means_mains(powered: FakeRoot) -> None:
    assert on_mains(powered.path) is False

    powered.write(f"{SUPPLIES}/ucsi-source-psy-USBC000:001/online", 1)
    assert on_mains(powered.path) is True

    powered.write(f"{SUPPLIES}/ucsi-source-psy-USBC000:001/online", 0)
    powered.write(f"{SUPPLIES}/AC0/online", 1)
    assert on_mains(powered.path) is True


def test_a_gamepads_battery_does_not_count(fake_root: FakeRoot) -> None:
    fake_root.write(f"{SUPPLIES}/hid-gamepad-battery/type", "Battery")
    fake_root.write(f"{SUPPLIES}/hid-gamepad-battery/scope", "Device")

    # Without supplies of the system's own the kernel takes it as supplied.
    assert on_mains(fake_root.path) is True

    fake_root.write(f"{SUPPLIES}/BAT0/type", "Battery")
    assert on_mains(fake_root.path) is False


def test_profiles_are_read_by_handler(powered: FakeRoot) -> None:
    assert platform_profiles(powered.path) == {"amd-pmf": "balanced", "asus-wmi": "balanced"}


def test_the_firmwares_profile_is_written_again_to_give_its_power_back(
    powered: FakeRoot,
) -> None:
    profile = powered.path / "sys/class/platform-profile/platform-profile-1/profile"
    profile.write_text("performance\n", encoding="utf-8")
    other = powered.path / "sys/class/platform-profile/platform-profile-0/profile"
    other.unlink()

    assert reset_to_profile(powered.path) is True
    assert profile.read_text(encoding="utf-8") == "performance\n"
    # Only asus-wmi's profile carries the firmware's power; amd-pmf's is left alone.
    assert not other.exists()


def test_without_asus_wmi_nothing_is_given_back(fake_root: FakeRoot) -> None:
    assert reset_to_profile(fake_root.path) is False
