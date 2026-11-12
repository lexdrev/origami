# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""The battery line of the Power tile: the charge is looked at all the while the plugin runs."""

import asyncio
import logging
import time
from collections.abc import Callable
from pathlib import Path

from origami.battery import BatteryWatch, Forecast, GameDrains, read_charge
from origami.blocks import Context
from origami.power import time_asleep
from origami.sysfs import read_int
from origami.tasks import BackgroundTask
from origami.tdp import ARMOURY, ATTRIBUTES

log = logging.getLogger(__name__)

LOOK_SECONDS = 10.0
SAVE_SECONDS = 300.0
"""The games' averages are saved this often while one changes, and as the game changes."""


class BatteryBlock:
    """Looks at the battery every few seconds, so the forecast is ready whenever a screen asks."""

    def __init__(
        self, context: Context, history: Path, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._root = context.root
        self._clock = clock
        self._drains = GameDrains(history)
        self._watch = BatteryWatch(self._drains)
        self._game: int | None = None
        self._forecast: Forecast | None = None
        self._saved_for: int | None = None
        self._saved_at = clock()
        self._looks = BackgroundTask("origami-battery", self._keep_looking)

    async def start(self) -> None:
        await asyncio.to_thread(self._drains.load)
        self._looks.start()

    def set_game(self, app_id: int | None) -> None:
        """Steam runs this game now, or none: its draw is measured and remembered as its own."""
        self._game = app_id

    def forecast(self) -> Forecast | None:
        """How long the battery lasts as of the last look; None on the charger."""
        return self._forecast

    def stop(self) -> None:
        self._looks.cancel()

    async def _keep_looking(self) -> None:
        try:
            while True:
                self._forecast = await asyncio.to_thread(self._look, self._game)
                await asyncio.sleep(LOOK_SECONDS)
        finally:
            # With nobody looking, the last forecast would be shown as the battery's for good.
            self._forecast = None

    def _look(self, game: int | None) -> Forecast | None:
        now = self._clock()
        # The sustained limit as asus-armoury caches it: the same for the same setting, whoever
        # set it, which is all a game's average needs to tell its TDPs apart.
        tdp = read_int(self._root / ARMOURY / ATTRIBUTES[0] / "current_value")
        forecast = self._watch.look(now, time_asleep(), read_charge(self._root), game=game, tdp=tdp)
        if game != self._saved_for or now - self._saved_at >= SAVE_SECONDS:
            self._saved_for, self._saved_at = game, now
            try:
                self._drains.save()
            except OSError as error:
                log.warning("Battery history not saved: %s", error)
        return forecast
