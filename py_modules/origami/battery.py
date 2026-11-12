# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""How long the battery lasts, from the energy it lost over the last minutes.

The gauge's power_now is the draw of one moment: in a menu or a calm scene it promises more time
than the game leaves. The forecast here divides what the battery lost by the time it took, over
five minutes at most, and counts down to a tenth of the charge, not to an empty battery. A game's
average draw at each TDP is kept between its runs, so its first minutes are told from the runs
before; without one the gauge's power_now stands in until enough is measured.

energy_now moves in steps of 16 mWh on the Ally X (read on the console), a step every two seconds
in a game, so a minute of them measures the draw within a few percent. Off the charger at a full
charge it stands still at energy_full for minutes (eighteen on the console, a game started
meanwhile) while power_now tells the draw, then makes up for a part of that time in one step and
stands again for a minute. A step after it stood is no draw: the measuring starts after it.
"""

import json
import logging
import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from origami.fsutil import atomic_write_text
from origami.jsonio import JsonValue, parse_object
from origami.power import SLEEP_THRESHOLD_SECONDS
from origami.sysfs import read_int, read_text
from origami.tdp import POWER_SUPPLIES

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

WINDOW_SECONDS = 300.0
MIN_SPAN_SECONDS = 60.0
"""A shorter span measures the gauge's steps more than the draw."""
RESERVE_PCT = 10
"""The charge the time is counted down to; under it, down to an empty battery."""
FOLD_SECONDS = 60.0
"""A game's draw goes into its average a minute at a time."""
REMEMBERED_MINUTES = 120
"""The weight an average may reach, so older play fades as the game is played on."""
STOOD_SECONDS = 30.0
"""A gauge that has not moved for this long would tell a draw under MIN_DRAIN_W: it stands."""
MIN_DRAIN_W = 3.0
MAX_DRAIN_W = 100.0
"""Awake, with its screen on, the console draws several watts, and its battery gives some tens.
Anything else is a gauge that stood still, had just woken or corrected its charge, not a draw."""
MICRO = 1_000_000


@dataclass(frozen=True, slots=True)
class Charge:
    """One look at the battery."""

    discharging: bool
    energy_uwh: int | None
    full_uwh: int | None
    power_uw: int | None


@dataclass(frozen=True, slots=True)
class Forecast:
    minutes_left: int
    until_pct: int
    """The charge the minutes count down to: the reserve, or zero once the charge is under it."""
    drain_w: float
    """What the whole console draws from the battery, as the minutes were counted."""


@dataclass(frozen=True, slots=True)
class Drain:
    watts: float
    minutes: int
    """How much play the average stands on, up to REMEMBERED_MINUTES."""


def find_battery(root: Path) -> Path | None:
    for supply in sorted((root / POWER_SUPPLIES).glob("*")):
        # A gamepad's battery is a supply of its device, not the console's.
        if read_text(supply / "type") == "Battery" and read_text(supply / "scope") != "Device":
            return supply
    return None


def read_charge(root: Path) -> Charge | None:
    battery = find_battery(root)
    if battery is None:
        return None
    return Charge(
        discharging=read_text(battery / "status") == "Discharging",
        energy_uwh=read_int(battery / "energy_now"),
        full_uwh=read_int(battery / "energy_full"),
        power_uw=read_int(battery / "power_now"),
    )


class GameDrains:
    """Every game's average draw from the battery at each TDP, kept on disk between its runs."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._drains: dict[tuple[int, int | None], Drain] = {}
        self._unsaved = False

    def load(self) -> None:
        try:
            self._drains = _parse(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError) as error:
            # Only averages, measured again as the games are played: the next save replaces them.
            log.warning("Battery history %s is unreadable, starting empty: %s", self._path, error)

    def known(self, game: int, tdp: int | None) -> Drain | None:
        return self._drains.get((game, tdp))

    def add_minute(self, game: int, tdp: int | None, watts: float) -> None:
        before = self._drains.get((game, tdp))
        if before is None:
            self._drains[game, tdp] = Drain(watts, 1)
        else:
            minutes = min(before.minutes + 1, REMEMBERED_MINUTES)
            average = before.watts + (watts - before.watts) / minutes
            self._drains[game, tdp] = Drain(average, minutes)
        self._unsaved = True

    def save(self) -> None:
        """Write the averages if any changed since the last save; raise OSError when it fails."""
        if not self._unsaved:
            return
        drains: list[JsonValue] = [
            {"app_id": game, "tdp": tdp, "watts": round(drain.watts, 2), "minutes": drain.minutes}
            for (game, tdp), drain in self._drains.items()
        ]
        document: dict[str, JsonValue] = {"version": SCHEMA_VERSION, "drains": drains}
        atomic_write_text(self._path, json.dumps(document, indent=2) + "\n")
        self._unsaved = False


class BatteryWatch:
    """Follows the charge look by look and tells how long it lasts.

    The measuring starts anew whenever the energy lost stops telling the draw to come: another
    game or TDP draws another power, sleep draws next to nothing while the clock stands still, and
    a charge that rose was on the charger meanwhile.
    """

    def __init__(self, drains: GameDrains) -> None:
        self._drains = drains
        self._samples: deque[tuple[float, int]] = deque()
        self._load: tuple[int | None, int | None] = (None, None)
        self._asleep = 0.0
        self._folded: tuple[float, int] | None = None
        """When the game's average took its last minute, and the energy then."""
        self._moved_at = 0.0
        """When the energy last differed from the look before."""

    def look(
        self, at: float, asleep: float, charge: Charge | None, *, game: int | None, tdp: int | None
    ) -> Forecast | None:
        """Take one look at the battery; None on the charger or while nothing tells the draw.

        `at` is a monotonic time and `asleep` the time spent asleep so far, both in seconds.
        """
        load = (game, tdp)
        anew = load != self._load or asleep - self._asleep > SLEEP_THRESHOLD_SECONDS
        self._load, self._asleep = load, asleep
        if anew or charge is None or not charge.discharging:
            self._forget()
        if charge is None or not charge.discharging or charge.energy_uwh is None:
            # A read of the energy that failed once leaves the minutes measured so far to count.
            return None
        energy = charge.energy_uwh
        if self._samples and energy > self._samples[-1][1]:
            self._forget()
        stood = at - self._moved_at > STOOD_SECONDS
        if not self._samples or energy != self._samples[-1][1]:
            self._moved_at = at
        if stood:
            # Nothing is measured while the gauge stands, and the step it then takes makes up
            # for that time: the measuring starts anew with every look until it has moved.
            self._forget()
        self._samples.append((at, energy))
        # The oldest look stays until the next one is as old as the window, so a full window is
        # never shorter than WINDOW_SECONDS.
        while len(self._samples) > 1 and at - self._samples[1][0] >= WINDOW_SECONDS:
            self._samples.popleft()
        self._fold(at, energy)
        watts = self._watts(charge.power_uw)
        if watts is None:
            return None
        reserve = None if not charge.full_uwh else charge.full_uwh * RESERVE_PCT // 100
        if reserve is not None and energy > reserve:
            left, until = energy - reserve, RESERVE_PCT
        else:
            left, until = energy, 0
        return Forecast(
            minutes_left=round(left / MICRO / watts * 60), until_pct=until, drain_w=round(watts, 1)
        )

    def _forget(self) -> None:
        self._samples.clear()
        self._folded = None

    def _fold(self, at: float, energy: int) -> None:
        """Add each full minute of a game's draw to its average."""
        if self._folded is None:
            self._folded = (at, energy)
            return
        since, before = self._folded
        if at - since < FOLD_SECONDS:
            return
        self._folded = (at, energy)
        game, tdp = self._load
        watts = _plausible(_watts(before - energy, at - since))
        if game is not None and watts is not None:
            self._drains.add_minute(game, tdp, watts)

    def _watts(self, power_uw: int | None) -> float | None:
        """The draw to count with: measured, and until the window fills, told in part before."""
        (first_at, first), (last_at, last) = self._samples[0], self._samples[-1]
        span = last_at - first_at
        measured = _plausible(_watts(first - last, span)) if span >= MIN_SPAN_SECONDS else None
        game, tdp = self._load
        known = None if game is None else self._drains.known(game, tdp)
        gauge = None if power_uw is None else _plausible(power_uw / MICRO)
        told = gauge if known is None else known.watts
        if measured is None or told is None:
            return measured if told is None else told
        share = min(1.0, span / WINDOW_SECONDS)
        return share * measured + (1 - share) * told


def _watts(energy_uwh: int, seconds: float) -> float:
    return energy_uwh / MICRO * 3600 / seconds


def _plausible(watts: float) -> float | None:
    return watts if MIN_DRAIN_W <= watts <= MAX_DRAIN_W else None


def _parse(text: str) -> dict[tuple[int, int | None], Drain]:
    try:
        document = parse_object(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON: {error}") from error
    if document.get("version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported version {document.get('version')!r}")
    entries = document.get("drains")
    if not isinstance(entries, list):
        raise ValueError("drains must be a list")
    drains: dict[tuple[int, int | None], Drain] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("a drain must be an object")
        data = cast("dict[str, object]", entry)
        game, tdp = data.get("app_id"), data.get("tdp")
        watts, minutes = data.get("watts"), data.get("minutes")
        if not _is_int(game) or not (tdp is None or _is_int(tdp)) or not _is_int(minutes):
            raise ValueError(f"malformed drain {entry!r}")
        if isinstance(watts, bool) or not isinstance(watts, int | float):
            raise ValueError(f"malformed drain {entry!r}")
        # json takes NaN and Infinity too; neither compares as plausible.
        if not math.isfinite(watts) or _plausible(watts) is None:
            raise ValueError(f"malformed drain {entry!r}")
        drains[cast("int", game), cast("int | None", tdp)] = Drain(
            float(watts), min(max(cast("int", minutes), 1), REMEMBERED_MINUTES)
        )
    return drains


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
