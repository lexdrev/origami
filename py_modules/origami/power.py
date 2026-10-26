# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""Noticing that the console woke up from sleep.

The boot-time clock keeps counting while the system sleeps and the monotonic clock does not,
so the gap between them grows by the time spent asleep. Comparing two clocks needs no
D-Bus client, which Decky's Python does not bundle.
"""

import asyncio
import time
from collections.abc import AsyncGenerator, Callable

POLL_SECONDS = 2.0
SLEEP_THRESHOLD_SECONDS = 1.0
"""A longer jump of the gap than the clocks drift apart in a poll."""


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
