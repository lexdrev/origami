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

The numbers of the hold are a console's own: how fast its fans turn at a speed asked, the least
they turn at, and on the first ROG Ally a floor of the firmware, which from 60 °C runs the fans at
about half speed whatever the curve asks (`HoldFans`, `Floor`).
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
"""Percent the Xbox Ally X's fans are never asked less than, which keeps them turning at their
slowest, about 3800 rpm. Asked for nothing they stop, a SoC under load then warms by half a degree
a second until a step starts them again, and the temperature swings (measured 2026-11-13)."""
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
HOLD_EASE = 3.0
"""Percent a look takes off the level found per °C under the target, twice what it adds over it.
Coming down too fast lets the SoC pass the target by a degree or two for a moment; coming down as
slowly as going up kept the fans loud for two minutes after a heavy scene (measured 2026-11-21)."""
HOLD_EASE_MOST = 10.0
"""Percent one look takes off the level found at most."""
HOLD_LEAN = 4
"""Percent of speed on top of the level found per °C over the target, and as much less under it:
the answer to a change now, while the level found catches up."""
HOLD_REWRITE = 2
"""Percent the level moves before the firmware gets a new curve."""
HOLD_FLOOR_NEAR = 0.5
"""°C around the ends of a firmware's floor that count as past them: a look comes every few
seconds, and the firmware may have gone on or off between two."""
HOLD_FLOOR_CLEAR = 2
"""°C under a floor's start where the hold keeps the SoC while it can: clear of the swing there."""
HOLD_FLOOR_COOLER = 1.0
"""°C cooler than that the floor has to keep the SoC, for HOLD_FLOOR_PATIENCE looks in a row,
before the hold tries the fans under the floor again."""
HOLD_FLOOR_PATIENCE = 12
HOLD_FASTER = 500
"""Rpm over the level's own speed that tell the firmware runs the fans, not the level."""


@dataclass(frozen=True, slots=True)
class Floor:
    """A speed the firmware runs the fans at by itself, whatever the curve asks."""

    at: int
    """°C from which the fans run at the floor at least."""
    back: int
    """°C the SoC cools to before the firmware lets the fans go."""
    percent: int
    """About the floor, in the curve's percent."""


@dataclass(frozen=True, slots=True)
class HoldFans:
    """What a hold knows of a console's fans, as measured on that console."""

    slowest: int
    """Percent the fans are never asked less than: asked for nothing, they stop."""
    rpm: tuple[tuple[int, int], ...]
    """How fast fan 1 turns at a speed asked: percent and rpm, from nothing to full speed."""
    floor: Floor | None = None

    def rpm_at(self, percent: float) -> float:
        """Fan 1's speed at a speed asked, on the line between the two measured around it."""
        for (low, slow), (high, fast) in pairwise(self.rpm):
            if percent <= high:
                return slow + (fast - slow) * (percent - low) / (high - low)
        return float(self.rpm[-1][1])


XBOX_ALLY_X = HoldFans(
    slowest=HOLD_SLOWEST,
    rpm=(
        (0, 0),
        (8, 3700),
        (15, 4000),
        (30, 4735),
        (45, 5460),
        (60, 6100),
        (70, 6600),
        (100, 8000),
    ),
)
ROG_ALLY = HoldFans(
    slowest=15,
    rpm=(
        (0, 0),
        (10, 3300),
        (15, 3500),
        (25, 4100),
        (30, 4400),
        (45, 5200),
        (60, 6000),
        (75, 6800),
        (90, 7400),
        (100, 7700),
    ),
    floor=Floor(at=60, back=56, percent=50),
)
"""The first ROG Ally, from its owner's recordings (2026-11-04 to 2026-11-22). From 60 °C its
firmware runs both fans at about 5300 rpm at least, whatever the curve asks, until the SoC is back
at 56 °C; under 60 °C the fans follow the curve. Full speed was never recorded: 7700 rpm is the
most seen, at 90%."""
HOLD_FANS = {"RC73XA": XBOX_ALLY_X, "RC74XA": XBOX_ALLY_X, "RC71L": ROG_ALLY}
"""The consoles whose fans hold a temperature, by board: the Xbox Ally X, where the hold was
measured, the X20, taken to have the same fans, and the ROG Ally. Other fans turn at other speeds
and may have floors of their own: there the curve follows its points."""


def hold_fans(board: str | None) -> HoldFans | None:
    """What the hold knows of a console's fans; None where they hold no temperature."""
    return None if board is None else HOLD_FANS.get(board)


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

    Too warm, and the level found goes up look by look; cooler than the target, and it comes down
    faster, to the slowest where the fans cannot let the SoC get that warm. At full speed they can
    do no more. On top of it the level leans with the temperature now, which answers a change at
    once, and while that brings the temperature back the level found waits.

    Where the firmware has a floor, the fans cannot run slower than it from the floor's start on.
    A target the SoC rests at with the fans slower than the floor is then held under the start
    instead, clear of it: there the fans obey, and a steady speed is quieter than the firmware
    taking them up and letting them go. Once the SoC is at the floor all the same, the hold aims at
    the target itself and asks the floor at least, until the SoC has cooled back or the floor
    keeps it cooler than the hold would. And while the fans turn faster than the level asks, the
    level found does not come down: it is the firmware that cools then, not the level.
    """

    def __init__(self, target: int, fans: HoldFans = XBOX_ALLY_X) -> None:
        self._target = target
        self._fans = fans
        self._found = float(HOLD_START)
        self._recent: deque[float] = deque(maxlen=HOLD_LOOKS)
        self._before: float | None = None
        """The temperature of the look before, to tell which way it goes."""
        self._floored = False
        """The SoC got to the firmware's floor and has not cooled back since."""
        self._cooler = 0
        """Looks in a row the floor kept the SoC cooler than the hold would."""
        self.level = HOLD_START
        """The level for the firmware's curve: it follows in steps, not every look."""

    @property
    def held(self) -> int:
        """The temperature held now: the target, or under the firmware's floor while it can be."""
        floor = self._fans.floor
        if floor is None or self._floored:
            return self._target
        return min(self._target, floor.at - HOLD_FLOOR_CLEAR)

    def aim(self, target: int) -> None:
        """Hold another temperature from the level found so far."""
        self._target = target

    def look(self, temp: float, rpm: int | None = None) -> int:
        """Take the SoC's temperature and fan 1's speed now; returns the level for the curve."""
        self._recent.append(temp)
        now = sum(self._recent) / len(self._recent)
        floor = self._fans.floor
        if floor is not None:
            self._meet(floor, temp, now)
        least = float(self._fans.slowest if floor is None or not self._floored else floor.percent)
        over = now - self.held
        nearing = 0.0 if self._before is None else (self._before - now) * (1 if over > 0 else -1)
        self._before = now
        if abs(over) > HOLD_REST and nearing * HOLD_AHEAD < abs(over):
            if over > 0:
                self._found += min(HOLD_MOST, HOLD_GAIN * over)
            elif not self._run_by_firmware(temp, rpm):
                self._found += max(-HOLD_EASE_MOST, HOLD_EASE * over)
        self._found = _within(self._found, least)
        asked = _within(self._found + HOLD_LEAN * over, least)
        at_an_end = asked in (least, float(FULL_SPEED))
        if abs(asked - self.level) >= HOLD_REWRITE or at_an_end:
            self.level = round(asked)
        return self.level

    def _meet(self, floor: Floor, temp: float, now: float) -> None:
        """Tell whether the firmware's floor runs the fans, as far as the temperature tells."""
        if temp >= floor.at - HOLD_FLOOR_NEAR:
            self._floored, self._cooler = True, 0
        elif temp <= floor.back - HOLD_FLOOR_NEAR:
            self._floored = False
        elif self._floored:
            under = min(self._target, floor.at - HOLD_FLOOR_CLEAR)
            waits = self._found <= floor.percent and now < under - HOLD_FLOOR_COOLER
            self._cooler = self._cooler + 1 if waits else 0
            if self._cooler >= HOLD_FLOOR_PATIENCE:
                # The firmware lets go about here, and slower fans can keep the SoC under it.
                self._floored = False

    def _run_by_firmware(self, temp: float, rpm: int | None) -> bool:
        """Whether the firmware's floor has the fans: they turn faster than the level asks, and
        the SoC is not yet as cool as the floor lets them go at."""
        floor = self._fans.floor
        if floor is None or rpm is None or temp <= floor.back - HOLD_FLOOR_NEAR:
            return False
        return rpm > self._fans.rpm_at(self.level) + HOLD_FASTER


def _within(percent: float, least: float) -> float:
    return min(float(FULL_SPEED), max(least, percent))


def fan_speed(root: Path) -> int | None:
    """Fan 1's speed in rpm, the CPU's fan; None unread."""
    device = find_hwmon(root, "asus")
    return None if device is None else read_int(device / "fan1_input")


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
