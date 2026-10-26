# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

import pytest

from origami import gamescope

from fakes import FakeDisplay, FakeRoot


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
def display(fake_root: FakeRoot, monkeypatch: pytest.MonkeyPatch) -> FakeDisplay:
    """gamescope's display; its socket belongs to another user than the plugin's root."""
    fake_root.write("tmp/.X11-unix/X0", "")
    fake = FakeDisplay()
    monkeypatch.setattr(gamescope, "run", fake.run)
    monkeypatch.setattr(gamescope.os, "geteuid", lambda: 0)
    return fake
