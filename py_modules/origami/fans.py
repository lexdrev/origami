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

The firmware draws no line between the points: the fans run at the speed of the last point the
temperature has passed, and keep what they had under the first one (measured 2026-11-13: with 20%
at 50 °C and 60% at 60 °C they ran at 20% at 57 °C).

Instead of the user's points the curve can hold a temperature. Between their slowest and their
fastest the fans move the SoC by 8 to 9 °C, and the SoC settles about a minute after a new speed
(measured 2026-11-13). `Hold` looks at the temperature every few seconds and finds the speed at
which it rests at the target, so the fans run as slow as the target allows. The firmware gets that
one speed for every temperature up to HOLD_NET degrees over the target, and steps to full speed
above: they answer a jump before the next look, and keep the SoC cool with ORIGAMI gone.
"""

from collections import deque
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import cast

from origami.jsonio import JsonValue, expect_bool
from origami.sysfs import find_hwmon, read_int

type Curve = tuple[tuple[int, int], ...]
"""The eight points the firmware takes: °C and speed in percent."""

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

HOLD_COOLEST, HOLD_WARMEST = 45, 75
"""The targets to choose from, in °C. Under the first no TDP a game runs at gets the SoC; over the
last the net would have to start before the target to be at SAFE_PERCENT by SAFE_FROM."""
HOLD_TARGET = 60
HOLD_NET = 4
"""°C over the target where the firmware's own steps begin: clear of the swing around the target,
or the fans would jump as the temperature crosses a step."""
HOLD_STEPS = ((0, 35), (1, 50), (2, 65), (3, 80), (4, 90), (6, 100))
"""The net: °C over its start, and the speed the fans run at from there if the level is lower."""
HOLD_SLOWEST = 8
"""Percent the fans are never asked less than, which keeps them turning at their slowest, about
3800 rpm. Asked for nothing they stop, a SoC under load then warms by half a degree a second until
a step starts them again, and the temperature swings (measured 2026-11-13)."""
HOLD_START = 40
"""The level a hold starts from: about the balanced curve's speed in a game."""
HOLD_LOOKS = 3
"""Looks the temperature is averaged over, so a spike of one look counts for a third."""
HOLD_REST = 0.3
"""°C around the target within which the level found rests."""
HOLD_AHEAD = 8
"""Looks ahead: while the temperature is to reach the target within them at the pace it goes, the
level found waits. Moved all the same, it overshoots, and the fans run faster than the target
asks for minutes."""
HOLD_GAIN = 1.5
"""Percent a look adds to the level found per °C over the target: the SoC follows the fans in about
a minute, and a level moved faster than that swings."""
HOLD_MOST = 6.0
"""Percent one look moves the level found at most."""
HOLD_LEAN = 4
"""Percent of speed on top of the level found per °C over the target, and as much less under it:
the answer to a change now, while the level found catches up."""
HOLD_REWRITE = 2
"""Percent the level moves before the firmware gets a new curve."""


@dataclass(frozen=True, slots=True)
class FanCurve:
    enabled: bool = True
    """Off gives the fans back to the firmware; the rest waits for the next time it is on."""
    points: tuple[int, ...] = BALANCE
    """Speed in percent at each of TEMPS."""
    hold: bool = False
    """Hold the SoC at `target` instead of following the points."""
    target: int = HOLD_TARGET
    """°C, HOLD_COOLEST to HOLD_WARMEST."""

    def __post_init__(self) -> None:
        check_points(self.points)
        check_target(self.target)

    @classmethod
    def from_json(cls, value: object) -> FanCurve:
        """Parse a fan curve sent by the frontend or saved; raise ValueError on bad input."""
        if not isinstance(value, dict):
            raise ValueError("fans must be an object")
        data = cast("dict[str, object]", value)
        points = data.get("points", list(BALANCE))
        if not isinstance(points, list):
            raise ValueError("points must be a list")
        # Points and target are checked as the curve is made (__post_init__).
        return cls(
            enabled=expect_bool("enabled", data.get("enabled", True)),
            points=cast("tuple[int, ...]", tuple(cast("list[object]", points))),
            hold=expect_bool("hold", data.get("hold", False)),
            target=cast("int", data.get("target", HOLD_TARGET)),
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "enabled": self.enabled,
            "points": list(self.points),
            "hold": self.hold,
            "target": self.target,
        }


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


def check_target(target: object) -> None:
    """Raise ValueError unless the target is one a hold may have."""
    if (
        not isinstance(target, int)
        or isinstance(target, bool)
        or not HOLD_COOLEST <= target <= HOLD_WARMEST
    ):
        raise ValueError(f"target must be °C from {HOLD_COOLEST} to {HOLD_WARMEST}")


def own_curve(points: tuple[int, ...]) -> Curve:
    """The user's points as the firmware takes them."""
    return (*zip(TEMPS, points, strict=True), TOP)


def hold_curve(target: int, level: int) -> Curve:
    """The curve that runs the fans at `level` percent up to the net over the target.

    The net's second step is at SAFE_PERCENT and never over SAFE_FROM °C, as HOLD_WARMEST sees to.
    """
    start = target + HOLD_NET
    net = tuple((start + over, max(level, least)) for over, least in HOLD_STEPS)
    return ((TEMPS[0], level), *net, TOP)


class Hold:
    """Finds the fan speed at which the SoC rests at the target.

    Too warm, and the level found goes up look by look; cooler than the target, and it comes down,
    to HOLD_SLOWEST where the fans cannot let the SoC get that warm. At full speed they can do no
    more. On top of it the level leans with the temperature now, which answers a change at once,
    and while that brings the temperature back the level found waits.
    """

    def __init__(self, target: int) -> None:
        self._target = target
        self._found = float(HOLD_START)
        self._recent: deque[float] = deque(maxlen=HOLD_LOOKS)
        self._before: float | None = None
        """The temperature of the look before, to tell which way it goes."""
        self.level = HOLD_START
        """The level for the firmware's curve: it follows in steps, not every look."""

    def aim(self, target: int) -> None:
        """Hold another temperature from the level found so far."""
        self._target = target

    def look(self, temp: float) -> int:
        """Take the SoC's temperature now; returns the level for the firmware's curve."""
        self._recent.append(temp)
        now = sum(self._recent) / len(self._recent)
        over = now - self._target
        nearing = 0.0 if self._before is None else (self._before - now) * (1 if over > 0 else -1)
        self._before = now
        if abs(over) > HOLD_REST and nearing * HOLD_AHEAD < abs(over):
            move = max(-HOLD_MOST, min(HOLD_MOST, HOLD_GAIN * over))
            self._found = _speed(self._found + move)
        asked = _speed(self._found + HOLD_LEAN * over)
        at_an_end = asked in (float(HOLD_SLOWEST), float(FULL_SPEED))
        if abs(asked - self.level) >= HOLD_REWRITE or at_an_end:
            self.level = round(asked)
        return self.level


def _speed(percent: float) -> float:
    return min(float(FULL_SPEED), max(float(HOLD_SLOWEST), percent))


def hottest(root: Path) -> float | None:
    """The warmer of the CPU and the GPU in °C: one chip, and either may lead; None unread."""
    readings = (
        read_int(device / "temp1_input")
        for name in ("k10temp", "amdgpu")
        if (device := find_hwmon(root, name)) is not None
    )
    temps = [reading / 1000 for reading in readings if reading is not None]
    return max(temps, default=None)


def curve_dir(root: Path) -> Path | None:
    """The hwmon device that takes custom fan curves; None where the firmware has none."""
    return find_hwmon(root, CURVE_HWMON)


def write_curve(root: Path, curve: Curve) -> None:
    """Send the curve to both fans and switch it on; raise OSError when the firmware refuses."""
    device = curve_dir(root)
    if device is None:
        raise OSError(f"No {CURVE_HWMON} here")
    for fan in FANS:
        for index, (temp, percent) in enumerate(curve, start=1):
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
