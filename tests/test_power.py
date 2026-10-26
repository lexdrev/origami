# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from contextlib import aclosing

from origami.power import resumes


def test_a_jump_of_the_sleep_gap_is_a_resume() -> None:
    # Gap between the boot-time and monotonic clocks: steady, then 30 s asleep, then steady.
    gaps = iter([5.0, 5.001, 5.002, 35.0, 35.001])

    async def scenario() -> int:
        count = 0
        async with aclosing(resumes(poll_seconds=0, asleep=lambda: next(gaps))) as wakes:
            async for _ in wakes:
                count += 1
                break
        return count

    assert asyncio.run(scenario()) == 1
    assert next(gaps) == 35.001
