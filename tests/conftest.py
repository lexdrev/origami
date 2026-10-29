# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

import pytest

from origami import cpu, gamescope

from fakes import FakeDisplay, FakeRoot


@pytest.fixture(autouse=True)
def quick_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lowered frequency cap is raised back at once instead of after a moment."""
    monkeypatch.setattr(cpu, "KICK_HOLD_SECONDS", 0)


@pytest.fixture
def fake_root(tmp_path: Path) -> FakeRoot:
    return FakeRoot(tmp_path / "root")


@pytest.fixture
def ally_x(fake_root: FakeRoot) -> FakeRoot:
    """ROG Xbox Ally X with values measured on the console (see HARDWARE.md)."""
    fake_root.write("sys/class/dmi/id/board_name", "RC73XA")
    fake_root.write("sys/class/dmi/id/product_name", "ROG Xbox Ally X RC73XA_RC73XA")
    armoury = "sys/class/firmware-attributes/asus-armoury/attributes"
    fake_root.write(f"{armoury}/ppt_pl1_spl/current_value", 17)
    fake_root.write("sys/devices/system/cpu/cpufreq/boost", 0)
    fake_root.write(
        "sys/module/hid_asus_ally/drivers/hid:asus_rog_ally/0003:0B05:1B4C.0004/vibration_intensity",
        "50 50",
    )
    fake_root.hwmon(3, "acpitz", temp1_input=53000)
    fake_root.hwmon(5, "amdgpu", power1_average=16_900_000, temp1_input=61000)
    fake_root.hwmon(6, "asus", fan1_input=4600, fan2_input=4700)
    fake_root.hwmon(7, "k10temp", temp1_input=61625)
    fake_root.write("proc/sys/kernel/osrelease", "7.2.9-ogc3.1.fc44.x86_64")
    fake_root.write(
        "usr/lib/os-release",
        'NAME="Bazzite"\nVERSION_ID="44"\nOSTREE_VERSION=\'44.20261023\'',
    )
    return fake_root


@pytest.fixture
def powered(ally_x: FakeRoot) -> FakeRoot:
    """The Ally X on the battery, its power attributes as on the console (HARDWARE.md, probe 20)."""
    armoury = "sys/class/firmware-attributes/asus-armoury/attributes"
    for name, current, low, high in (
        ("ppt_pl1_spl", 17, 7, 35),
        ("ppt_pl2_sppt", 21, 13, 45),
        ("ppt_pl3_fppt", 26, 19, 55),
    ):
        ally_x.write(f"{armoury}/{name}/current_value", current)
        ally_x.write(f"{armoury}/{name}/min_value", low)
        ally_x.write(f"{armoury}/{name}/max_value", high)
    supplies = "sys/class/power_supply"
    ally_x.write(f"{supplies}/AC0/type", "Mains")
    ally_x.write(f"{supplies}/AC0/online", 0)
    ally_x.write(f"{supplies}/BAT0/type", "Battery")
    ally_x.write(f"{supplies}/BAT0/status", "Discharging")
    ally_x.write(f"{supplies}/BAT0/capacity", 54)
    ally_x.write(f"{supplies}/BAT0/energy_now", 40_000_000)
    ally_x.write(f"{supplies}/BAT0/energy_full", 74_348_000)
    ally_x.write(f"{supplies}/BAT0/energy_full_design", 80_003_000)
    ally_x.write(f"{supplies}/BAT0/power_now", 20_000_000)
    ally_x.write(f"{supplies}/ucsi-source-psy-USBC000:001/type", "USB")
    ally_x.write(f"{supplies}/ucsi-source-psy-USBC000:001/online", 0)
    profiles = "sys/class/platform-profile"
    ally_x.write(f"{profiles}/platform-profile-0/name", "amd-pmf")
    ally_x.write(f"{profiles}/platform-profile-0/profile", "balanced")
    ally_x.write(f"{profiles}/platform-profile-1/name", "asus-wmi")
    ally_x.write(f"{profiles}/platform-profile-1/profile", "balanced")
    for index in range(4):
        policy = f"sys/devices/system/cpu/cpufreq/policy{index}"
        ally_x.write(f"{policy}/scaling_max_freq", 2_000_000)
        ally_x.write(f"{policy}/cpuinfo_max_freq", 2_000_000)
        ally_x.write(f"{policy}/amd_pstate_max_freq", 5_090_910)
        ally_x.write(f"{policy}/scaling_cur_freq", 1_990_000)
    return ally_x


@pytest.fixture
def display(fake_root: FakeRoot, monkeypatch: pytest.MonkeyPatch) -> FakeDisplay:
    """gamescope's display; its socket belongs to another user than the plugin's root."""
    fake_root.write("tmp/.X11-unix/X0", "")
    fake = FakeDisplay()
    monkeypatch.setattr(gamescope, "run", fake.run)
    monkeypatch.setattr(gamescope, "run_blocking", fake.run_blocking)
    monkeypatch.setattr(gamescope.os, "geteuid", lambda: 0)
    return fake
