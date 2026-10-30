# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Gamepad tile: the handles' vibration strength, the trigger rumble and the gyroscope."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from origami.blocks import Context
from origami.gyro import GyroState, read_gyro_state, remove_fix, restart_inputplumber, write_fix
from origami.proc import CommandError
from origami.rumble import Attach, RumbleProgram, RumbleSettings
from origami.settings import Settings
from origami.triggers import (
    TAP_GAP_SECONDS,
    TAP_SECONDS,
    TAPS_IN_TEST,
    TriggerRumble,
    TriggerState,
    read_trigger_state,
    start_trigger_pulse,
)
from origami.vibration import (
    GRIP_AT_GAME_FULL,
    PULSE_SECONDS,
    Vibration,
    apply_vibration,
    original_vibration,
    read_driver_strength,
    start_pulse,
    stop_rumble,
)

log = logging.getLogger(__name__)


class GamepadBlock:
    """Sends the vibration and the rumble program to the controller, and fixes the gyroscope.

    The display block talks to the controller's MCU too, so reports to it are sent under the
    shared `controller_lock`. `board` names the console's board once ORIGAMI has started.
    """

    def __init__(
        self,
        context: Context,
        controller_lock: asyncio.Lock,
        *,
        program: Path,
        attach_bpf: Attach,
        board: Callable[[], Awaitable[str | None]],
    ) -> None:
        self._context = context
        self._controller_lock = controller_lock
        self._board = board
        self._rumble = RumbleProgram(context.root, program, attach_bpf)
        self._pulsing = False

    async def send(self, before: Settings, after: Settings) -> None:
        """Send a changed vibration strength and rumble program before the settings keep them."""
        if after.vibration is not None and after.vibration != before.vibration:
            await self._send_vibration(after.vibration)
        triggers_changed = after.trigger_rumble != before.trigger_rumble
        if triggers_changed or after.vibration != before.vibration:
            try:
                await self._send_rumble(after)
            except (OSError, RuntimeError) as error:
                # The grips' lift is extra: their strength has reached the MCU already.
                if triggers_changed:
                    raise
                log.warning("Grips not lifted: %s", error)

    async def send_gyro(self, before: Settings, after: Settings) -> None:
        # Unset and off are the same axes: switching off a fix never set changes nothing.
        if bool(after.gyro_fix) != bool(before.gyro_fix):
            await self.set_gyro(on=bool(after.gyro_fix))

    async def restore(self, settings: Settings) -> None:
        """Send the saved vibration and rumble program again, at start and after sleep.

        Failures are only logged: the controller may be gone, or another plugin drives it now.
        """
        vibration = settings.vibration
        if vibration is not None:
            try:
                await self._send_vibration(vibration)
            except (OSError, RuntimeError) as error:
                log.warning("Vibration not restored: %s", error)
        if vibration is not None or settings.trigger_rumble is not None:
            try:
                await self._send_rumble(settings)
            except (OSError, RuntimeError) as error:
                log.warning("Rumble program not restored: %s", error)

    def give_back_vibration(self, owner: str | None) -> None:
        """The handles' strength as it was before ORIGAMI; blocks briefly.

        A plugin that sets it now keeps it as it set it: only ORIGAMI's record goes.
        """
        journal = self._context.journal
        if not journal.recorded("gamepad", "vibration"):
            return
        original = original_vibration(journal.original("gamepad", "vibration"))
        try:
            if owner is None:
                apply_vibration(self._context.root, original)
            journal.forget("gamepad", "vibration")
        except OSError as error:
            log.warning("Vibration strength not given back: %s", error)

    async def close_rumble(self) -> None:
        """Take the rumble program off the controller: games rumble as before ORIGAMI."""
        await asyncio.to_thread(self._rumble.close)

    async def gyro_state(self) -> GyroState:
        """Whether the gyroscope's axes need ORIGAMI here, and what ORIGAMI has done about them."""
        board = await self._board()
        return await asyncio.to_thread(read_gyro_state, self._context.root, board)

    async def trigger_state(self) -> TriggerState:
        """Whether the triggers here have motors ORIGAMI can rumble."""
        board = await self._board()
        return await asyncio.to_thread(read_trigger_state, self._context.root, board)

    async def set_gyro(self, *, on: bool) -> None:
        """Make the gyroscope's axes follow the setting; InputPlumber restarts for a new file."""
        journal, root = self._context.journal, self._context.root
        state = await self.gyro_state()
        match on, state:
            case True, GyroState.WRONG | GyroState.OUTDATED:
                await asyncio.to_thread(journal.record, "gamepad", "gyro", None)
                await asyncio.to_thread(write_fix, root)
            case False, GyroState.FIXED | GyroState.OUTDATED:
                await asyncio.to_thread(remove_fix, root)
                await asyncio.to_thread(journal.forget, "gamepad", "gyro")
            case True, GyroState.FIXED:
                return
            case True, _:
                raise RuntimeError(f"ORIGAMI cannot fix the gyroscope here ({state})")
            case _:
                return
        await restart_inputplumber()

    async def restore_gyro(self, settings: Settings) -> None:
        """Keep the axes as set: InputPlumber may have been updated, or the file may be gone."""
        try:
            await self.set_gyro(on=bool(settings.gyro_fix))
        except (CommandError, OSError, RuntimeError, TimeoutError) as error:
            log.warning("Gyroscope not restored: %s", error)

    def remove_gyro_fix(self) -> None:
        """Remove ORIGAMI's axes for uninstall; InputPlumber takes the stock ones when it starts."""
        try:
            if remove_fix(self._context.root):
                self._context.journal.forget("gamepad", "gyro")
        except OSError as error:
            log.warning("Gyroscope fix not removed: %s", error)

    async def test_vibration(self) -> None:
        """Rumble the handles for a second, so the strength can be felt without a game.

        The controller keeps a rumble until it is told to stop, so the pulse always ends with a
        stop, also when the call is cancelled or the plugin unloads. A press during it is ignored.
        The rumble program would rumble the triggers with the handles, so they keep still meanwhile.
        """
        if self._pulsing:
            return
        self._pulsing = True
        try:
            await asyncio.to_thread(self._start_handle_pulse)
            await asyncio.sleep(PULSE_SECONDS)
        finally:
            self._end_pulse()
            await asyncio.to_thread(self._rumble.unmute)

    async def test_trigger_rumble(self, trigger_rumble: TriggerRumble | None) -> None:
        """Rumble the triggers at their level as a game's full rumble would: a second, or taps."""
        if self._pulsing or trigger_rumble is None or not trigger_rumble.enabled:
            return
        root = self._context.root
        self._pulsing = True
        try:
            if trigger_rumble.taps:
                # Taps as a game's shots give them, not one long rumble.
                # The last tap ends with the test.
                for tap in range(TAPS_IN_TEST):
                    if tap:
                        await asyncio.to_thread(stop_rumble, root)
                        await asyncio.sleep(TAP_GAP_SECONDS)
                    await asyncio.to_thread(start_trigger_pulse, root, trigger_rumble)
                    await asyncio.sleep(TAP_SECONDS)
            else:
                await asyncio.to_thread(start_trigger_pulse, root, trigger_rumble)
                await asyncio.sleep(PULSE_SECONDS)
        finally:
            self._end_pulse()

    def stop(self) -> None:
        """Stop a vibration test at once and take the rumble program off the controller."""
        self._end_pulse()
        self._rumble.close()

    async def _send_vibration(self, vibration: Vibration) -> None:
        owner = (await self._context.conflicts()).vibration
        if owner is not None:
            raise RuntimeError(f"{owner} sets the vibration strength, so ORIGAMI leaves it alone")
        async with self._controller_lock:
            await asyncio.to_thread(self._record_vibration)
            await asyncio.to_thread(apply_vibration, self._context.root, vibration)

    async def _send_rumble(self, settings: Settings) -> None:
        """Have the rumble program fill the triggers as chosen and lift the grips ORIGAMI drives.

        The grips are lifted only under ORIGAMI's own strength: with another plugin setting it, or
        before the user sets one, games rumble the grips as before.
        """
        owners = await self._context.conflicts()
        trigger_rumble = settings.trigger_rumble or TriggerRumble()
        own_grips = (
            settings.vibration is not None
            and settings.vibration.enabled
            and owners.vibration is None
        )
        rumble = RumbleSettings(
            *trigger_rumble.strengths(),
            grips=GRIP_AT_GAME_FULL if own_grips else 0,
            taps=trigger_rumble.enabled and trigger_rumble.taps,
        )
        async with self._controller_lock:
            if owners.triggers is not None and trigger_rumble.enabled:
                await asyncio.to_thread(self._rumble.close)
                raise RuntimeError(
                    f"{owners.triggers} rumbles the triggers, so ORIGAMI leaves them alone"
                )
            await asyncio.to_thread(self._rumble.apply, rumble)

    def _record_vibration(self) -> None:
        journal = self._context.journal
        if journal.recorded("gamepad", "vibration"):
            return
        # The MCU cannot be asked, so the original is what the driver last took.
        strength = read_driver_strength(self._context.root)
        journal.record("gamepad", "vibration", None if strength is None else list(strength))

    def _start_handle_pulse(self) -> None:
        self._rumble.mute_triggers()
        start_pulse(self._context.root)

    def _end_pulse(self) -> None:
        # Sent at once, without awaiting: an await could be cut short and leave the motors running.
        if not self._pulsing:
            return
        self._pulsing = False
        try:
            stop_rumble(self._context.root)
        except OSError as error:
            log.warning("Vibration test not stopped: %s", error)
