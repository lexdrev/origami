# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""ORIGAMI's power settings, held through sleep, the charger, profile changes and game starts.

Nothing tells ORIGAMI when the firmware drops its TDP, so the keeper looks every two seconds, and
at once when the kernel reports a supply change, at what can: the clocks (sleep), the supplies (the
charger), the platform profiles, the limits that read back (someone else wrote) and the power the
SoC draws (the firmware runs another limit). After
each of these it writes ORIGAMI's limits again, a moment later than the writer it follows: Steam
writes 35 W as the charger changes in performance (probe 20), a profile written last brings back
its own power, and a game start goes through Steam's own writes (B05). Writing the same limits
again applies them again. With the CPU boost off it keeps the cores under their cap (B03).

The boot-time clock keeps counting while the system sleeps and the monotonic clock does not,
so the gap between them grows by the time spent asleep. Comparing two clocks needs no
D-Bus client, which Decky's Python does not bundle.
"""

import asyncio
import logging
import math
import threading
import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from origami.cpu import fastest_core, frequency_cap, read_boost, write_boost
from origami.jsonio import JsonValue, expect_bool
from origami.tdp import (
    BATTERY_TDP,
    MAX_TDP,
    MIN_TDP,
    Limits,
    limits_for,
    on_mains,
    platform_profiles,
    read_limits,
    read_ranges,
    soc_power,
    write_limits,
)

log = logging.getLogger(__name__)

POLL_SECONDS = 2.0
SLEEP_THRESHOLD_SECONDS = 1.0
"""A longer jump of the gap than the clocks drift apart in a poll."""

DEFAULT_TDP = 17
"""The firmware's own sustained limit, and the Balance preset."""
RESUME_SETTLE_SECONDS = 2.0
CHARGER_SETTLE_SECONDS = 0.0
"""Steam writes its TDP from 0.1 to 2.6 s after the charger changes (probe 21), so ORIGAMI writes
at once and answers Steam's write when it lands, within a look."""
PROFILE_SETTLE_SECONDS = 1.5
GAME_REWRITE_SECONDS = (2.0, 5.0, 10.0)
"""Steam writes its own limits and the profile as a game starts, in no fixed order (B05)."""
QUIET_SECONDS = 5.0
"""After a change ORIGAMI follows, a write over its limits is Steam settling, not a dispute."""
WATCH_SECONDS = 30.0
WATCH_LOOK_SECONDS = 0.25
"""After a change the keeper looks this often: Steam writes late, and the CPU's cap slips again
about ten seconds later (probe 21)."""
FOREIGN_WINDOW_SECONDS = 60.0
FOREIGN_LIMIT = 3
"""Writes over ORIGAMI's limits in a window that it answers; one more and it stops holding them."""
OVER_MARGIN_W = 2.0
OVER_SECONDS = 10.0
"""How long the SoC may draw more than the boost limit before ORIGAMI writes the limits again."""
OVER_INTERVAL_SECONDS = 60.0
CAP_SETTLE_SECONDS = 1.0
ESCAPE_KHZ = 150_000
"""How far over its cap a core may run before the cap counts as lost."""
ESCAPES_TO_PROGRAM = 2
"""Looks in a row with a core over its cap; one alone may be a core changing speed."""
CAP_INTERVAL_SECONDS = 5.0
MIN_LOOK_SECONDS = 0.05


def time_asleep() -> float:
    return time.clock_gettime(time.CLOCK_BOOTTIME) - time.monotonic()


async def resumes(
    *, poll_seconds: float = POLL_SECONDS, asleep: Callable[[], float] = time_asleep
) -> AsyncGenerator[None]:
    """Yield shortly after each resume from sleep."""
    before = asleep()
    while True:
        await asyncio.sleep(poll_seconds)
        now = asleep()
        if now - before > SLEEP_THRESHOLD_SECONDS:
            yield
        before = now


@dataclass(frozen=True, slots=True)
class Power:
    """What the user chose on the Power screen."""

    tdp: int = DEFAULT_TDP
    """The sustained limit in watts."""
    headroom: bool = True
    """Short boosts above the TDP, as from the factory; off, all three limits are the TDP."""
    cpu_boost: bool | None = None
    """The CPU's frequency boost; None until the user chooses, and ORIGAMI leaves the flag alone."""

    @classmethod
    def from_json(cls, value: object) -> Power:
        """Parse power settings sent by the frontend or saved; raise ValueError on bad input."""
        if not isinstance(value, dict):
            raise ValueError("power must be an object")
        data = cast("dict[str, object]", value)
        defaults = cls()
        tdp = data.get("tdp", defaults.tdp)
        if not isinstance(tdp, int) or isinstance(tdp, bool) or not MIN_TDP <= tdp <= MAX_TDP:
            raise ValueError(f"tdp must be watts from {MIN_TDP} to {MAX_TDP}")
        boost = data.get("cpu_boost", defaults.cpu_boost)
        return cls(
            tdp=tdp,
            headroom=expect_bool("headroom", data.get("headroom", defaults.headroom)),
            cpu_boost=None if boost is None else expect_bool("cpu_boost", boost),
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {"tdp": self.tdp, "headroom": self.headroom, "cpu_boost": self.cpu_boost}


MAX_GAME_NAME = 200
"""Characters of a game's name kept for the list of profiles."""


@dataclass(frozen=True, slots=True)
class GamePower:
    """A game's own power settings, made as a copy of the general ones when it is first chosen."""

    app_id: int
    """Steam's app id; non-Steam shortcuts have one as well."""
    name: str
    """The game's name as Steam showed it, for the list while the game is not running."""
    power: Power
    active: bool = True
    """The game runs with this profile; off, it runs with the general settings and this waits."""

    @classmethod
    def from_json(cls, value: object) -> GamePower:
        """Parse a game's profile sent by the frontend or saved; raise ValueError on bad input."""
        if not isinstance(value, dict):
            raise ValueError("a game's power must be an object")
        data = cast("dict[str, object]", value)
        app_id = data.get("app_id")
        if not isinstance(app_id, int) or isinstance(app_id, bool) or app_id <= 0:
            raise ValueError("app_id must be a positive Steam app id")
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("a game's power needs the game's name")
        return cls(
            app_id=app_id,
            name=name.strip()[:MAX_GAME_NAME],
            power=Power.from_json(data.get("power")),
            active=expect_bool("active", data.get("active", True)),
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "app_id": self.app_id,
            "name": self.name,
            "power": self.power.to_json(),
            "active": self.active,
        }


@dataclass(frozen=True, slots=True)
class PowerTarget:
    """What the keeper holds: the power settings, and whether ORIGAMI owns the TDP."""

    power: Power
    tdp: bool
    """ORIGAMI writes the TDP; off, it keeps only the CPU boost and its cap."""
    battery_high_tdp: bool = False
    """The TDP may go over BATTERY_TDP on the battery too."""
    steam_slider: bool = False
    """Steam's TDP slider is on and writes as it moves. ORIGAMI keeps the TDP all the same: it looks
    often and answers the slider at once, and never takes its writes for a writer to give way to."""

    def tdp_for(self, *, mains: bool) -> int:
        if mains or self.battery_high_tdp:
            return self.power.tdp
        return min(self.power.tdp, BATTERY_TDP)


@dataclass(frozen=True, slots=True)
class HeldPower:
    """What the keeper holds now, for the Power screen."""

    limits: Limits | None
    """ORIGAMI's limits for the supply in use; None while it does not write the TDP."""
    battery_capped: bool
    """On the battery the TDP is held at BATTERY_TDP instead of the one chosen."""
    contested: bool
    """Something else keeps writing the TDP, so ORIGAMI stopped until the settings change."""


@dataclass(frozen=True, slots=True)
class _Seen:
    mains: bool
    profiles: dict[str, str]
    asleep: float


class PowerKeeper:
    """Holds the power settings; tick() takes one look at the hardware and blocks while it does.

    The plugin calls tick() from a thread every POLL_SECONDS, and the other methods from its event
    loop, so a lock keeps them apart. The CPU's cap needs a pause between two writes, which a
    thread must not sleep through, so tick() only says when it is due and the plugin programs it.
    """

    def __init__(
        self,
        root: Path,
        *,
        clock: Callable[[], float] = time.monotonic,
        asleep: Callable[[], float] = time_asleep,
    ) -> None:
        self._root = root
        self._clock = clock
        self._asleep = asleep
        self._lock = threading.Lock()
        self._target: PowerTarget | None = None
        self._seen: _Seen | None = None
        self._due: list[tuple[float, str]] = []
        """When to write the limits, and why."""
        self._written: dict[bool, Limits] = {}
        """The limits ORIGAMI wrote last to the charger's set (True) and the battery's (False)."""
        self._last_event = -math.inf
        self._last_write = -math.inf
        self._foreign: list[float] = []
        self._contested = False
        self._over_since: float | None = None
        self._last_power_fix = -math.inf
        self._cap_due: float | None = None
        self._escapes = 0
        self._last_cap = -math.inf
        self._held = HeldPower(None, battery_capped=False, contested=False)

    def hold(self, target: PowerTarget | None) -> None:
        """Hold these settings from the next tick on; None holds nothing."""
        with self._lock:
            if target == self._target:
                return
            before, self._target = self._target, target
            self._contested = False
            self._foreign.clear()
            now = self._clock()
            self._due.append((now, "settings"))
            # The cap needs programming when the keeper starts and when the boost goes off.
            if before is None or target is None or before.power.cpu_boost != target.power.cpu_boost:
                self._cap_due = now
            if target is None or not target.tdp:
                self._held = HeldPower(None, battery_capped=False, contested=False)

    def game_started(self) -> None:
        """Write the limits again as Steam settles a game that starts, and keep the cap."""
        with self._lock:
            now = self._clock()
            self._last_event = now
            self._due += [(now + delay, "game started") for delay in GAME_REWRITE_SECONDS]
            self._cap_due = now + CAP_SETTLE_SECONDS

    def write_again(self, reason: str) -> None:
        """Write the limits again at the next look: the profile's own may have come back."""
        with self._lock:
            self._due.append((self._clock(), reason))

    def held(self) -> HeldPower:
        with self._lock:
            return self._held

    def next_look(self) -> float:
        """Seconds until the keeper should look again: at the next write due, or after a poll."""
        with self._lock:
            now = self._clock()
            due = [at for at, _ in self._due]
            if self._cap_due is not None:
                due.append(self._cap_due)
            soonest = min(due, default=now + POLL_SECONDS)
            watching = now - self._last_event < WATCH_SECONDS or (
                self._target is not None and self._target.steam_slider
            )
            poll = WATCH_LOOK_SECONDS if watching else POLL_SECONDS
            return min(max(soonest - now, MIN_LOOK_SECONDS), poll)

    def tick(self) -> str | None:
        """Take one look and write what has to be written; return why the cap is due, if it is."""
        with self._lock:
            target = self._target
            if target is None:
                return None
            now = self._clock()
            mains = on_mains(self._root)
            self._notice_changes(now, mains=mains)
            try:
                if target.tdp:
                    self._hold_tdp(now, target, mains=mains)
                else:
                    self._due.clear()
                return self._hold_cpu(now, target)
            except OSError as error:
                log.warning("Power settings not held: %s", error)
                return None

    def _notice_changes(self, now: float, *, mains: bool) -> None:
        seen = _Seen(mains, platform_profiles(self._root), self._asleep())
        before, self._seen = self._seen, seen
        if before is None:
            return
        if seen.asleep - before.asleep > SLEEP_THRESHOLD_SECONDS:
            self._follow(now, RESUME_SETTLE_SECONDS, "resumed")
        if seen.mains != before.mains:
            self._follow(now, CHARGER_SETTLE_SECONDS, "charger in" if mains else "charger out")
        if seen.profiles != before.profiles:
            self._follow(now, PROFILE_SETTLE_SECONDS, "platform profile changed")

    def _follow(self, now: float, settle: float, reason: str) -> None:
        self._last_event = now
        self._due.append((now + settle, reason))
        self._cap_due = now + CAP_SETTLE_SECONDS

    def _hold_tdp(self, now: float, target: PowerTarget, *, mains: bool) -> None:
        reason = self._take_due(now)
        ranges = read_ranges(self._root)
        if ranges is None:
            return
        tdp = target.tdp_for(mains=mains)
        want = limits_for(tdp, headroom=target.power.headroom, ranges=ranges)
        if self._contested:
            reason = None
        elif reason is None:
            reason = self._check_written(now, target, want, mains=mains) or self._check_power(
                now, want
            )
        if reason is not None:
            write_limits(self._root, want)
            self._written[mains] = want
            self._last_write = now
            self._over_since = None
            log.info("TDP %d / %d / %d W written: %s", want.spl, want.sppt, want.fppt, reason)
        self._held = HeldPower(
            want, battery_capped=tdp < target.power.tdp, contested=self._contested
        )

    def _take_due(self, now: float) -> str | None:
        ready = [reason for at, reason in self._due if at <= now]
        self._due = [(at, reason) for at, reason in self._due if at > now]
        return ready[0] if ready else None

    def _check_written(
        self, now: float, target: PowerTarget, want: Limits, *, mains: bool
    ) -> str | None:
        current = read_limits(self._root)
        if current is None or current == want or self._due:
            # A write of ORIGAMI's comes anyway.
            return None
        if self._written.get(mains) != want:
            # This set never got these limits (a write failed): nobody wrote over ORIGAMI.
            return "limits differ"
        written = f"written over with {current.spl} / {current.sppt} / {current.fppt} W"
        if now - self._last_event < QUIET_SECONDS:
            return f"{written}, settling"
        if target.steam_slider:
            return f"{written} by Steam's slider"
        self._foreign = [at for at in self._foreign if now - at < FOREIGN_WINDOW_SECONDS]
        self._foreign.append(now)
        if len(self._foreign) > FOREIGN_LIMIT:
            self._contested = True
            log.warning("Something else keeps writing TDP (%s); ORIGAMI stops holding it", current)
            return None
        return written

    def _check_power(self, now: float, want: Limits) -> str | None:
        """Write the limits again when the SoC draws more than they allow, for long."""
        power = soc_power(self._root)
        if power is None or power <= want.sppt + OVER_MARGIN_W:
            self._over_since = None
            return None
        if self._over_since is None:
            self._over_since = now
        if now - self._over_since < OVER_SECONDS or now - self._last_write < OVER_SECONDS:
            return None
        if now - self._last_power_fix < OVER_INTERVAL_SECONDS:
            return None
        self._last_power_fix = now
        return f"the SoC drew {power:.1f} W"

    def _hold_cpu(self, now: float, target: PowerTarget) -> str | None:
        boost = read_boost(self._root)
        if boost is None:
            self._cap_due = None
            return None
        wanted = target.power.cpu_boost
        if wanted is not None and boost != wanted:
            write_boost(self._root, on=wanted)
            log.info("CPU boost switched %s", "on" if wanted else "off")
            self._cap_due = now + CAP_SETTLE_SECONDS
            return None
        if boost:
            self._cap_due = None
            return None
        reason = self._cap_reason(now)
        if reason is not None:
            self._cap_due = None
            self._escapes = 0
            self._last_cap = now
        return reason

    def _cap_reason(self, now: float) -> str | None:
        if self._cap_due is not None and self._cap_due <= now:
            return "after a change"
        cap, fastest = frequency_cap(self._root), fastest_core(self._root)
        if cap is None or fastest is None or fastest <= cap + ESCAPE_KHZ:
            self._escapes = 0
            return None
        self._escapes += 1
        if self._escapes < ESCAPES_TO_PROGRAM or now - self._last_cap < CAP_INTERVAL_SECONDS:
            return None
        return f"a core ran at {fastest // 1000} MHz over the {cap // 1000} MHz cap"
