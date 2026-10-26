# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""Live hardware readings for the main screen. Read-only."""

from dataclasses import dataclass
from pathlib import Path

from origami.sysfs import find_hwmon, read_int, read_text

ARMOURY = Path("sys/class/firmware-attributes/asus-armoury/attributes")
CPU_BOOST = Path("sys/devices/system/cpu/cpufreq/boost")
ALLY_HID = Path("sys/module/hid_asus_ally/drivers/hid:asus_rog_ally")


@dataclass(frozen=True, slots=True)
class PowerTelemetry:
    tdp_limit_w: int | None
    """Sustained limit (SPL) as cached by asus-armoury; may differ from what firmware applies."""
    package_power_w: float | None
    cpu_boost: bool | None


@dataclass(frozen=True, slots=True)
class FanTelemetry:
    speeds_rpm: list[int]
    cpu_temp_c: float | None
    gpu_temp_c: float | None


@dataclass(frozen=True, slots=True)
class GamepadTelemetry:
    vibration_pct: tuple[int, int] | None
    """Left and right handle strength as reported by the hid-asus-ally driver."""


@dataclass(frozen=True, slots=True)
class Telemetry:
    power: PowerTelemetry
    fans: FanTelemetry
    gamepad: GamepadTelemetry


def read_telemetry(root: Path) -> Telemetry:
    amdgpu = find_hwmon(root, "amdgpu")
    return Telemetry(
        power=PowerTelemetry(
            tdp_limit_w=read_int(root / ARMOURY / "ppt_pl1_spl" / "current_value"),
            package_power_w=_scaled(amdgpu, "power1_average", 1_000_000),
            cpu_boost=_flag(root / CPU_BOOST),
        ),
        fans=_read_fans(root, amdgpu),
        gamepad=GamepadTelemetry(vibration_pct=_read_vibration(root)),
    )


def _read_fans(root: Path, amdgpu: Path | None) -> FanTelemetry:
    asus = find_hwmon(root, "asus")
    speeds: list[int] = []
    if asus is not None:
        # fan1 is the CPU fan, fan2 the GPU fan (labels cpu_fan / gpu_fan).
        speeds = [rpm for n in (1, 2) if (rpm := read_int(asus / f"fan{n}_input")) is not None]
    return FanTelemetry(
        speeds_rpm=speeds,
        cpu_temp_c=_scaled(find_hwmon(root, "k10temp"), "temp1_input", 1000),
        gpu_temp_c=_scaled(amdgpu, "temp1_input", 1000),
    )


def _read_vibration(root: Path) -> tuple[int, int] | None:
    for attribute in sorted((root / ALLY_HID).glob("*/vibration_intensity")):
        text = read_text(attribute)
        if text is None:
            continue
        match text.split():
            case [left, right] if left.isdigit() and right.isdigit():
                return int(left), int(right)
            case _:
                return None
    return None


def _scaled(hwmon: Path | None, attribute: str, divisor: int) -> float | None:
    if hwmon is None:
        return None
    raw = read_int(hwmon / attribute)
    return None if raw is None else raw / divisor


def _flag(path: Path) -> bool | None:
    raw = read_int(path)
    return None if raw is None else raw != 0
