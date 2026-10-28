# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""Live hardware readings for the main screen. Read-only."""

from dataclasses import dataclass
from pathlib import Path

from origami.sysfs import find_hwmon, read_int, read_text
from origami.tdp import POWER_SUPPLIES, on_mains
from origami.vibration import read_driver_strength

ARMOURY = Path("sys/class/firmware-attributes/asus-armoury/attributes")
CPU_BOOST = Path("sys/devices/system/cpu/cpufreq/boost")


@dataclass(frozen=True, slots=True)
class BatteryTelemetry:
    percent: int | None
    charging: bool
    minutes_left: int | None
    """Until empty at the power drawn now; None on the charger or while nothing is drawn."""
    capacity_pct: int | None
    """Full charge now against the design's, the battery's wear."""


@dataclass(frozen=True, slots=True)
class PowerTelemetry:
    tdp_limit_w: int | None
    """Sustained limit (SPL) as cached by asus-armoury; may differ from what firmware applies."""
    package_power_w: float | None
    cpu_boost: bool | None
    on_battery: bool
    battery: BatteryTelemetry | None


@dataclass(frozen=True, slots=True)
class FanTelemetry:
    speeds_rpm: list[int]
    cpu_temp_c: float | None
    gpu_temp_c: float | None


@dataclass(frozen=True, slots=True)
class GamepadTelemetry:
    vibration_pct: tuple[int, int] | None
    """Left and right handle strength as the hid-asus-ally driver last took it."""


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
            on_battery=not on_mains(root),
            battery=_read_battery(root),
        ),
        fans=_read_fans(root, amdgpu),
        gamepad=GamepadTelemetry(vibration_pct=read_driver_strength(root)),
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


def _find_battery(root: Path) -> Path | None:
    for supply in sorted((root / POWER_SUPPLIES).glob("*")):
        # A gamepad's battery is a supply of its device, not the console's.
        if read_text(supply / "type") == "Battery" and read_text(supply / "scope") != "Device":
            return supply
    return None


def _read_battery(root: Path) -> BatteryTelemetry | None:
    battery = _find_battery(root)
    if battery is None:
        return None
    status = read_text(battery / "status")
    energy, full = read_int(battery / "energy_now"), read_int(battery / "energy_full")
    design, power = read_int(battery / "energy_full_design"), read_int(battery / "power_now")
    minutes = None
    if status == "Discharging" and energy is not None and power:
        minutes = round(energy / power * 60)
    return BatteryTelemetry(
        percent=read_int(battery / "capacity"),
        charging=status == "Charging",
        minutes_left=minutes,
        capacity_pct=round(full / design * 100) if full is not None and design else None,
    )


def _scaled(hwmon: Path | None, attribute: str, divisor: int) -> float | None:
    if hwmon is None:
        return None
    raw = read_int(hwmon / attribute)
    return None if raw is None else raw / divisor


def _flag(path: Path) -> bool | None:
    raw = read_int(path)
    return None if raw is None else raw != 0
