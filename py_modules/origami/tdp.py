# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""The SoC's three power limits, written straight to asus-armoury (BUGS.md, B04 and B05).

asus-armoury keeps one set of limits for the charger and one for the battery, reads and writes the
set of the supply in use, and sends nothing to the firmware when the supply changes (its source,
HARDWARE.md). The firmware applies the limits written last until a platform profile is written:
that brings back the profile's own power, balanced about 17 W and performance up to 45 W, while
the attributes still read the old limits. So what reads back is what was written to this set, not
what the firmware applies. Balanced holds any limit up to 35 W, on the charger and on the battery
alike (probe 20), so ORIGAMI leaves the profile to the user.
"""

from dataclasses import dataclass
from pathlib import Path

from origami.sysfs import find_hwmon, read_int, read_text

ARMOURY = Path("sys/class/firmware-attributes/asus-armoury/attributes")
ATTRIBUTES = ("ppt_pl1_spl", "ppt_pl2_sppt", "ppt_pl3_fppt")
"""Sustained limit, short boost (seconds) and peak, in watts."""
PLATFORM_PROFILES = Path("sys/class/platform-profile")
FIRMWARE_PROFILE = "asus-wmi"
"""The platform profile handler whose profile the firmware's power follows."""
POWER_SUPPLIES = Path("sys/class/power_supply")

MIN_TDP = 7
MAX_TDP = 35
BATTERY_TDP = 25
"""Highest TDP on the battery unless the user allows more: ORIGAMI's guard, not the firmware's."""
SPPT_HEADROOM = 4
FPPT_HEADROOM = 9
"""The factory's boost and peak above the sustained limit (17 / 21 / 26 W)."""


@dataclass(frozen=True, slots=True)
class Limits:
    spl: int
    sppt: int
    fppt: int


@dataclass(frozen=True, slots=True)
class Range:
    low: int
    high: int

    def clamp(self, watts: int) -> int:
        return min(max(watts, self.low), self.high)


def read_limits(root: Path) -> Limits | None:
    """The limits last written to the set of the supply in use; None without asus-armoury."""
    values = [read_int(root / ARMOURY / name / "current_value") for name in ATTRIBUTES]
    spl, sppt, fppt = values
    if spl is None or sppt is None or fppt is None:
        return None
    return Limits(spl, sppt, fppt)


def read_ranges(root: Path) -> tuple[Range, Range, Range] | None:
    """What the firmware takes for each limit on the supply in use; the charger's boost from 14."""
    ranges: list[Range] = []
    for name in ATTRIBUTES:
        low = read_int(root / ARMOURY / name / "min_value")
        high = read_int(root / ARMOURY / name / "max_value")
        if low is None or high is None:
            return None
        ranges.append(Range(low, high))
    spl, sppt, fppt = ranges
    return spl, sppt, fppt


def limits_for(tdp: int, *, headroom: bool, ranges: tuple[Range, Range, Range]) -> Limits:
    """The three limits for a TDP, within what the firmware takes.

    Without the headroom all three are the TDP; below the firmware's lowest boost and peak (13 or 14
    and 19 W) those stay at their lowest.
    """
    spl_range, sppt_range, fppt_range = ranges
    spl = spl_range.clamp(tdp)
    sppt, fppt = (spl + SPPT_HEADROOM, spl + FPPT_HEADROOM) if headroom else (spl, spl)
    return Limits(spl, sppt_range.clamp(sppt), fppt_range.clamp(fppt))


def write_limits(root: Path, limits: Limits) -> None:
    """Send the limits to the firmware, in Steam's order; raise OSError when it refuses one."""
    for name, watts in zip(ATTRIBUTES, (limits.spl, limits.sppt, limits.fppt), strict=True):
        (root / ARMOURY / name / "current_value").write_text(f"{watts}\n", encoding="utf-8")


def soc_power(root: Path) -> float | None:
    """The SoC's power now in watts as amdgpu measures it: what the limits cap."""
    amdgpu = find_hwmon(root, "amdgpu")
    raw = None if amdgpu is None else read_int(amdgpu / "power1_average")
    return None if raw is None else raw / 1_000_000


def on_mains(root: Path) -> bool:
    """Whether the console runs from a charger, as the kernel decides for asus-armoury.

    As power_supply_is_system_supplied: supplies of a device (a gamepad's battery) do not count, any
    other supply that is not a battery and is online means a charger, and with no supplies at all
    the system counts as supplied.
    """
    try:
        supplies = sorted((root / POWER_SUPPLIES).iterdir())
    except OSError:
        return True
    counted = False
    for supply in supplies:
        if read_text(supply / "scope") == "Device":
            continue
        counted = True
        if read_text(supply / "type") != "Battery" and read_int(supply / "online") not in (None, 0):
            return True
    return not counted


def platform_profiles(root: Path) -> dict[str, str]:
    """The profile of each platform profile handler, by the handler's name."""
    try:
        handlers = sorted((root / PLATFORM_PROFILES).iterdir())
    except OSError:
        return {}
    profiles: dict[str, str] = {}
    for handler in handlers:
        name, profile = read_text(handler / "name"), read_text(handler / "profile")
        if name is not None and profile is not None:
            profiles[name] = profile
    return profiles


def reset_to_profile(root: Path) -> bool:
    """Give the firmware its profile's own power back; False without the handler.

    Writing the profile it has sends it to the firmware again (the kernel always passes it on).
    asus-wmi then switches its own fan curves off, as on every profile written.
    """
    try:
        handlers = sorted((root / PLATFORM_PROFILES).iterdir())
    except OSError:
        return False
    for handler in handlers:
        if read_text(handler / "name") == FIRMWARE_PROFILE:
            profile = read_text(handler / "profile")
            if profile is None:
                return False
            (handler / "profile").write_text(f"{profile}\n", encoding="utf-8")
            return True
    return False
