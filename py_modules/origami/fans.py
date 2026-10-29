# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""ORIGAMI's fan curve: one curve for both fans, held through profile changes (BUGS.md, B07).

The factory curve stops at about 78% even at 94 °C and spins louder than needed at middle
temperatures. asus-wmi takes eight points per fan in hwmon asus_custom_fan_curve: pwm1 is the CPU's
fan, pwm2 the GPU's, temperatures in °C and speeds 0-255. Writing a point sets that fan back to the
firmware's own curve, so the points go first and pwmN_enable = 1 after; enabling checks that neither
temperatures nor speeds fall, and the firmware follows within about 6 s and keeps the curve through
sleep (probe 16). A platform profile written by anyone switches the custom curves off, so the keeper
looks every few seconds and enables the curve again. pwmN_enable = 2 gives the fans back to the
firmware; 3 would load the factory points too, and with them the profile's own power (probe 16).
"""

from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import cast

from origami.jsonio import JsonValue, expect_bool
from origami.sysfs import find_hwmon, read_int

TEMPS = (30, 40, 50, 60, 70, 80, 90)
"""Temperatures of the points the user sets, in °C."""
TOP = (100, 100)
"""The eighth point, never set by the user: full speed at 100 °C."""
FULL_SPEED = 100
SAFE_FROM = 80
SAFE_PERCENT = 50
"""From SAFE_FROM °C on, a point is never below SAFE_PERCENT."""
BALANCE = (0, 10, 25, 40, 55, 75, 100)
"""The curve ORIGAMI starts with the first time it is switched on."""
FANS = (1, 2)
CUSTOM, FIRMWARE = 1, 2
"""Values of pwmN_enable: the custom curve, the firmware's own."""
POLL_SECONDS = 5.0
CURVE_HWMON = "asus_custom_fan_curve"


@dataclass(frozen=True, slots=True)
class FanCurve:
    enabled: bool = True
    """Off gives the fans back to the firmware; the points wait for the next time it is on."""
    points: tuple[int, ...] = BALANCE
    """Speed in percent at each of TEMPS."""

    def __post_init__(self) -> None:
        check_points(self.points)

    @classmethod
    def from_json(cls, value: object) -> FanCurve:
        """Parse a fan curve sent by the frontend or saved; raise ValueError on bad input."""
        if not isinstance(value, dict):
            raise ValueError("fans must be an object")
        data = cast("dict[str, object]", value)
        points = data.get("points", list(BALANCE))
        if not isinstance(points, list):
            raise ValueError("points must be a list")
        # Checked as the curve is made (__post_init__).
        speeds = cast("tuple[int, ...]", tuple(cast("list[object]", points)))
        return cls(enabled=expect_bool("enabled", data.get("enabled", True)), points=speeds)

    def to_json(self) -> dict[str, JsonValue]:
        return {"enabled": self.enabled, "points": list(self.points)}


def check_points(points: tuple[object, ...]) -> None:
    """Raise ValueError unless the points make a curve the firmware takes, keeping the SoC cool."""
    if len(points) != len(TEMPS):
        raise ValueError(f"A fan curve has {len(TEMPS)} points")
    for point in points:
        if not isinstance(point, int) or isinstance(point, bool) or not 0 <= point <= FULL_SPEED:
            raise ValueError("A fan speed is a percentage from 0 to 100")
    speeds = cast("tuple[int, ...]", points)
    if any(later < earlier for earlier, later in pairwise(speeds)):
        raise ValueError("A fan curve must not fall")
    if any(
        speed < SAFE_PERCENT for temp, speed in zip(TEMPS, speeds, strict=True) if temp >= SAFE_FROM
    ):
        raise ValueError(f"From {SAFE_FROM} °C the fans run at least at {SAFE_PERCENT}%")


def curve_dir(root: Path) -> Path | None:
    """The hwmon device that takes custom fan curves; None where the firmware has none."""
    return find_hwmon(root, CURVE_HWMON)


def write_curve(root: Path, points: tuple[int, ...]) -> None:
    """Send the curve to both fans and switch it on; raise OSError when the firmware refuses."""
    device = curve_dir(root)
    if device is None:
        raise OSError(f"No {CURVE_HWMON} here")
    pairs = [*zip(TEMPS, points, strict=True), TOP]
    for fan in FANS:
        for index, (temp, percent) in enumerate(pairs, start=1):
            (device / f"pwm{fan}_auto_point{index}_temp").write_text(f"{temp}\n", encoding="utf-8")
            (device / f"pwm{fan}_auto_point{index}_pwm").write_text(
                f"{(percent * 255 + 50) // 100}\n", encoding="utf-8"
            )
    for fan in FANS:
        (device / f"pwm{fan}_enable").write_text(f"{CUSTOM}\n", encoding="utf-8")


def curve_on(root: Path) -> bool:
    """Whether both fans follow the custom curve; a profile written since switches it off."""
    device = curve_dir(root)
    return device is not None and all(
        read_int(device / f"pwm{fan}_enable") == CUSTOM for fan in FANS
    )


def give_back(root: Path) -> None:
    """Let the firmware run the fans on its own curve again; raise OSError when it refuses."""
    device = curve_dir(root)
    if device is None:
        return
    for fan in FANS:
        (device / f"pwm{fan}_enable").write_text(f"{FIRMWARE}\n", encoding="utf-8")
