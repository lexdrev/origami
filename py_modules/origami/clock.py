# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""The crackle after sleep when the hardware clock keeps local time (BUGS.md, B14).

With the RTC in local time, as Windows keeps it beside Linux, the system clock comes back from
sleep off by the time zone's offset. chrony then slews it at up to 1/12, for hours, and the audio
clock follows the slewed one: PipeWire feeds the speakers too fast and they crackle (measured 12/11
of 48 kHz on the console). Stepping the clock right after the resume ends it. The RTC's mode stays:
switching it to UTC would put Windows' clock off.
"""

import asyncio
import logging
import time
from pathlib import Path

from origami.proc import CommandError, run

log = logging.getLogger(__name__)

ADJTIME = Path("etc/adjtime")
CHRONYC = Path("usr/bin/chronyc")
STEP_TIMEOUT_SECONDS = 5
MODE_LINE = 2
"""The line of /etc/adjtime that says UTC or LOCAL, counted from 0."""


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


async def step() -> None:
    """Set the system clock to chrony's time at once instead of slewing it."""
    try:
        async with asyncio.timeout(STEP_TIMEOUT_SECONDS):
            await run("chronyc", "makestep")
    except (CommandError, TimeoutError) as error:
        log.warning("Clock not stepped after sleep: %s", error)
        return
    log.info("Clock stepped after sleep")
