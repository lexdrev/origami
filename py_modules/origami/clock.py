# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""The crackle after sleep when the hardware clock keeps local time (BUGS.md, B14).

With the RTC in local time, as Windows keeps it beside Linux, the system clock comes back from
sleep off by the time zone's offset. chrony then slews it at up to 1/12, for hours, and the audio
clock follows the slewed one: PipeWire feeds the speakers too fast and they crackle (measured 12/11
of 48 kHz on the console). Stepping the clock ends it. The RTC's mode stays: switching it to UTC
would put Windows' clock off.

chrony only learns the clock is off from its first measurement after the wake, once the network is
back (6 s on the console), and its makestep steps no more than it is slewing. So after a resume
ORIGAMI watches chrony's tracking and steps the clock as soon as it is off: every 2 s at first,
then every 30 s for an hour, for a console that wakes without a network and finds one later.
The same watch starts when the fix is switched on, so a clock chrony slews right then is
stepped at once.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from origami.proc import CommandError, run

log = logging.getLogger(__name__)

ADJTIME = Path("etc/adjtime")
CHRONYC = Path("usr/bin/chronyc")
STEP_TIMEOUT_SECONDS = 5
MODE_LINE = 2
"""The line of /etc/adjtime that says UTC or LOCAL, counted from 0."""
STEP_THRESHOLD_SECONDS = 1.0
"""Fedora's chrony.conf steps from 1 s too, but only in its first three updates."""
WATCH_SECONDS = 120
"""How long after a resume ORIGAMI looks every POLL_SECONDS for chrony's first measurement."""
POLL_SECONDS = 2.0
LATE_WATCH_SECONDS = 3600
"""How long after that it still looks, every LATE_POLL_SECONDS: the network may come back late."""
LATE_POLL_SECONDS = 30.0
TRACKING_FIELDS = 5


class Runner(Protocol):
    """origami.proc.run, as the clock calls it."""

    def __call__(self, *args: str) -> Awaitable[str]: ...


@dataclass(frozen=True, slots=True)
class Tracking:
    """What `chronyc -c tracking` tells of the clock."""

    measured: float
    """When chrony took in its last measurement (Ref time)."""
    offset: float
    """How far off the system clock is: what chrony still slews (System time), in seconds."""

    @classmethod
    def parse(cls, text: str) -> Tracking:
        """Parse the CSV line; raise ValueError when it is not one."""
        fields = text.strip().split(",")
        if len(fields) < TRACKING_FIELDS:
            raise ValueError(f"chronyc tracking said {text.strip()!r}")
        return cls(measured=float(fields[3]), offset=float(fields[4]))


def local_rtc(root: Path) -> bool:
    """Whether the hardware clock keeps local time: the third line of /etc/adjtime says so."""
    try:
        lines = (root / ADJTIME).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return False
    return len(lines) > MODE_LINE and lines[MODE_LINE].strip() == "LOCAL"


def crackles_after_sleep(root: Path, *, offset_seconds: int | None = None) -> bool:
    """Whether this system has the bug: local RTC, a zone other than UTC+0, and chrony to slew."""
    offset = time.localtime().tm_gmtoff if offset_seconds is None else offset_seconds
    return local_rtc(root) and offset != 0 and (root / CHRONYC).exists()


async def step_when_off(
    runner: Runner = run,
    *,
    watch_seconds: float = WATCH_SECONDS,
    poll_seconds: float = POLL_SECONDS,
    late_watch_seconds: float = LATE_WATCH_SECONDS,
    late_poll_seconds: float = LATE_POLL_SECONDS,
) -> None:
    """Step the clock once chrony finds it off, instead of letting it slew.

    Runs after a resume and when the fix is switched on.
    """
    try:
        offset = await _first_offset(
            runner, (watch_seconds, poll_seconds), (late_watch_seconds, late_poll_seconds)
        )
    except TimeoutError:
        log.info(
            "Clock not checked: chrony measured nothing in %d s",
            watch_seconds + late_watch_seconds,
        )
        return
    except (CommandError, ValueError) as error:
        log.warning("Clock not checked: %s", error)
        return
    if offset is None:
        return
    try:
        async with asyncio.timeout(STEP_TIMEOUT_SECONDS):
            await runner("chronyc", "makestep")
    except (CommandError, TimeoutError) as error:
        log.warning("Clock not stepped: %s", error)
        return
    log.info("Clock stepped: it was %.1f s off", abs(offset))


async def _first_offset(
    runner: Runner, early: tuple[float, float], late: tuple[float, float]
) -> float | None:
    """chrony's offset as soon as the clock is off; None once a new measurement finds it right.

    `early` and `late` are how long to watch and how often to look, one after the other; raises
    TimeoutError when chrony measured nothing in all that time.
    """
    first = now = await _tracking(runner)
    for watch_seconds, poll_seconds in (early, late):
        try:
            async with asyncio.timeout(watch_seconds):
                while abs(now.offset) < STEP_THRESHOLD_SECONDS:
                    if now.measured != first.measured:
                        return None
                    await asyncio.sleep(poll_seconds)
                    now = await _tracking(runner)
                return now.offset
        except TimeoutError:
            continue
    raise TimeoutError


async def _tracking(runner: Runner) -> Tracking:
    return Tracking.parse(await runner("chronyc", "-c", "tracking"))
