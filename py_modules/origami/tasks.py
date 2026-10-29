# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import logging
from collections.abc import Callable, Coroutine

log = logging.getLogger(__name__)


class BackgroundTask:
    """Work that runs while a feature is on; a failure is logged instead of lost."""

    def __init__(self, name: str, work: Callable[[], Coroutine[None, None, None]]) -> None:
        self._name = name
        self._work = work
        self._task: asyncio.Task[None] | None = None

    async def run_while(self, *, on: bool) -> None:
        if on:
            self.start()
        else:
            await self.stop()

    def start(self) -> None:
        """Start the work unless it runs; work that ended or failed starts again."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._work(), name=self._name)
            self._task.add_done_callback(self._log_failure)

    async def stop(self) -> None:
        """Cancel the work and wait until it has cleaned up."""
        task = self.cancel()
        if task is not None:
            await asyncio.wait({task})

    def cancel(self) -> asyncio.Task[None] | None:
        """Cancel the work without waiting for it; returns the cancelled task, if any."""
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
        return task

    def _log_failure(self, task: asyncio.Task[None]) -> None:
        if not task.cancelled() and (error := task.exception()) is not None:
            log.error("%s stopped", self._name, exc_info=error)
