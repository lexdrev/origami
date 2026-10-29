# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import logging

import pytest

from origami.tasks import BackgroundTask


def test_work_that_failed_is_logged_and_starts_again(caplog: pytest.LogCaptureFixture) -> None:
    runs: list[int] = []

    async def work() -> None:
        runs.append(len(runs))
        if len(runs) == 1:
            raise RuntimeError("broken")
        await asyncio.Event().wait()

    async def scenario() -> None:
        task = BackgroundTask("test-work", work)
        await task.run_while(on=True)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert "test-work stopped" in caplog.text

        await task.run_while(on=True)
        await asyncio.sleep(0)
        assert runs == [0, 1]

        await task.run_while(on=True)
        await asyncio.sleep(0)
        assert runs == [0, 1]
        await task.stop()

    with caplog.at_level(logging.ERROR):
        asyncio.run(scenario())


def test_stopping_waits_for_the_work_to_clean_up() -> None:
    cleaned: list[bool] = []

    async def work() -> None:
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.append(True)

    async def scenario() -> None:
        task = BackgroundTask("test-work", work)
        task.start()
        await asyncio.sleep(0)
        await task.stop()
        assert cleaned == [True]

    asyncio.run(scenario())
