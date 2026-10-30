# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Power tile: the TDP and the CPU boost held as set, for the running game's own profile too."""

import asyncio
import logging
from contextlib import aclosing, suppress

from origami.blocks import Context
from origami.cpu import program_cap, read_boost, write_boost
from origami.power import POLL_SECONDS, HeldPower, PowerKeeper, PowerTarget
from origami.settings import Settings
from origami.tasks import BackgroundTask
from origami.tdp import read_limits, reset_to_profile
from origami.uevents import supply_changes

log = logging.getLogger(__name__)


def power_settings_changed(before: Settings, after: Settings) -> bool:
    return (before.power, before.battery_high_tdp, before.game_power) != (
        after.power,
        after.battery_high_tdp,
        after.game_power,
    )


class PowerBlock:
    """Holds the power through the keeper, which looks in a thread when it asks to or news comes."""

    def __init__(self, context: Context) -> None:
        self._context = context
        self._keeper = PowerKeeper(context.root)
        self._steam_tdp_limit = False
        self._game: int | None = None
        """The game Steam runs now, whose own power applies while it has an active profile."""
        self._look_now = asyncio.Event()
        """Wakes the keeper before its next look: a supply changed, or there is news to write."""
        self._hold = BackgroundTask("origami-power", self._hold_power)
        self._supplies = BackgroundTask("origami-supplies", self._watch_supplies)

    def held(self) -> HeldPower:
        """The limits ORIGAMI holds now, for the Power screen."""
        return self._keeper.held()

    async def set_steam_tdp_limit(self, settings: Settings, *, on: bool) -> None:
        """Steam's TDP slider was switched on or off (in the performance profile, where it works).

        While ORIGAMI manages the TDP, it keeps it: the slider's writes are answered at once, and
        the Power screen says the slider does nothing. Steam sets the TDP once "Manage TDP" is off.
        """
        if on == self._steam_tdp_limit:
            return
        self._steam_tdp_limit = on
        log.info("Steam's TDP slider is %s", "on: ORIGAMI writes over it" if on else "off")
        await self.follow(settings)

    async def set_game(self, settings: Settings, app_id: int | None) -> None:
        """Steam runs this game now, or none: the power follows the game's own profile, if any."""
        if app_id == self._game:
            return
        self._game = app_id
        own = settings.power_for(app_id) is not settings.power
        log.info(
            "Running game: %s, power: %s", app_id or "none", "its own profile" if own else "general"
        )
        await self.follow(settings)

    def game_started(self) -> None:
        """Steam started a game: it writes its own limits meanwhile, so ORIGAMI writes again."""
        self._keeper.game_started()
        self._look_now.set()

    def write_again(self, reason: str) -> None:
        """Have the keeper write the limits at its next look; safe from a worker thread."""
        self._keeper.write_again(reason)

    def look(self) -> None:
        """Have the keeper look at once; on the event loop only."""
        self._look_now.set()

    async def follow(self, settings: Settings) -> None:
        """Hold the power as set, unless another plugin owns it; the journal remembers first.

        With neither the TDP nor the boost left to ORIGAMI, after "restore everything" for one, the
        keeper holds nothing, and the CPU's frequency cap is not ORIGAMI's to program either.
        """
        power = settings.power_for(self._game)
        if (await self._context.conflicts()).power is not None or (
            settings.manage_tdp is not True and power.cpu_boost is None
        ):
            target = None
        else:
            target = PowerTarget(
                power,
                tdp=settings.manage_tdp is True,
                battery_high_tdp=settings.battery_high_tdp,
                steam_slider=self._steam_tdp_limit,
            )
            await asyncio.to_thread(self._record, target)
        self._keeper.hold(target)
        self._look_now.set()
        await self._hold.run_while(on=target is not None)

    def give_back_tdp(self, owner: str | None) -> None:
        """Let the firmware run its platform profile's own power again; blocks briefly.

        A plugin that sets the power now keeps it as it set it: only ORIGAMI's record goes.
        """
        journal = self._context.journal
        if not journal.recorded("power", "tdp"):
            return
        if owner is None:
            try:
                reset_to_profile(self._context.root)
            except OSError as error:
                log.warning("TDP not given back to the platform profile: %s", error)
                return
            log.info("TDP given back to the platform profile")
        journal.forget("power", "tdp")

    def give_back_boost(self, owner: str | None) -> None:
        """The CPU boost as it was before ORIGAMI, unless a plugin sets the power now."""
        journal = self._context.journal
        original = journal.original("power", "cpu_boost")
        if owner is None and isinstance(original, bool):
            try:
                write_boost(self._context.root, on=original)
            except OSError as error:
                log.warning("CPU boost not given back: %s", error)
                return
        journal.forget("power", "cpu_boost")

    def stop(self) -> None:
        self._hold.cancel()
        self._supplies.cancel()
        # A look at the hardware still running in its thread ends before this returns.
        self._keeper.hold(None)

    def _record(self, target: PowerTarget) -> None:
        journal, root = self._context.journal, self._context.root
        if target.tdp and read_limits(root) is not None:
            # The firmware's power before ORIGAMI is its platform profile's own, not a value.
            journal.record("power", "tdp", None)
        if target.power.cpu_boost is not None and not journal.recorded("power", "cpu_boost"):
            journal.record("power", "cpu_boost", read_boost(root))

    async def _hold_power(self) -> None:
        """Let the keeper look when it asks to, and at once when something changes."""
        self._supplies.start()
        try:
            while True:
                # Cleared before the look: a change meanwhile brings the next one at once.
                self._look_now.clear()
                cap_due = await asyncio.to_thread(self._keeper.tick)
                if cap_due is not None:
                    try:
                        await program_cap(self._context.root)
                        log.info("CPU frequency cap programmed again: %s", cap_due)
                    except OSError as error:
                        log.warning("CPU frequency cap not programmed: %s", error)
                with suppress(TimeoutError):
                    async with asyncio.timeout(self._keeper.next_look()):
                        await self._look_now.wait()
        finally:
            self._supplies.cancel()

    async def _watch_supplies(self) -> None:
        try:
            async with aclosing(supply_changes()) as changes:
                async for _ in changes:
                    self._look_now.set()
        except OSError as error:
            log.warning(
                "No kernel events about the charger, it is looked for every %s s: %s",
                POLL_SECONDS,
                error,
            )
