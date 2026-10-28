# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import logging
from collections.abc import Awaitable, Mapping
from contextlib import aclosing
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from origami.buttons import Button, ButtonAction, button_presses
from origami.decky_plugins import (
    LIGHTING_OWNERS,
    SATURATION_OWNERS,
    TRIGGER_OWNERS,
    VIBRATION_OWNERS,
    enabled_plugins,
)
from origami.device import Device, read_device
from origami.gyro import GyroState, read_gyro_state, remove_fix, restart_inputplumber, write_fix
from origami.hid_bpf import HidBpfProgram
from origami.inputplumber import Chord, press_chord
from origami.journal import Change, ChangeJournal
from origami.jsonio import JsonValue
from origami.lighting import Lighting, apply_lighting
from origami.magnifier import Magnifier
from origami.power import resumes
from origami.proc import CommandError
from origami.rumble import PROGRAM, Attach, RumbleProgram, RumbleSettings
from origami.saturation import read_saturation, write_saturation
from origami.settings import Settings, SettingsStore
from origami.tasks import BackgroundTask
from origami.telemetry import Telemetry, read_telemetry
from origami.triggers import (
    TriggerRumble,
    TriggerState,
    read_trigger_state,
    start_trigger_pulse,
)
from origami.versions import Versions, read_versions
from origami.vibration import (
    GRIP_AT_GAME_FULL,
    PULSE_SECONDS,
    Vibration,
    apply_vibration,
    read_driver_strength,
    start_pulse,
    stop_rumble,
)

log = logging.getLogger(__name__)

QAM_PRESSED = "qam_pressed"
"""Event sent to the frontend on every press of the quick access button while QAM assist is on."""
BUTTON_ACTION = "button_action"
"""Event sent to the frontend with the action of a button ORIGAMI drives, on every press of it."""

CHORDS = {
    ButtonAction.SCREENSHOT: Chord.SCREENSHOT,
    ButtonAction.KEYBOARD: Chord.KEYBOARD,
    ButtonAction.L5: Chord.L5,
}
"""Actions that are buttons Steam knows, which ORIGAMI presses through InputPlumber."""

RESUME_SETTLE_SECONDS = 2.0
"""The driver resets the controller on resume; ORIGAMI sends its settings after that."""


class Emit(Protocol):
    """Sends an event with its arguments to the frontend (decky.emit)."""

    def __call__(self, event: str, /, *args: JsonValue) -> Awaitable[None]: ...


@dataclass(frozen=True, slots=True)
class Environment:
    """Where the backend runs: the filesystem root, Decky's folders and the versions."""

    root: Path
    settings_dir: Path
    data_dir: Path
    decky_home: Path
    plugin_dir: Path
    """ORIGAMI's own folder, with the HID-BPF programs in bin/."""
    version: str
    decky_version: str | None


@dataclass(frozen=True, slots=True)
class Info:
    version: str
    device: Device
    versions: Versions


@dataclass(frozen=True, slots=True)
class Conflicts:
    """Enabled plugins that drive hardware ORIGAMI also drives; ORIGAMI then leaves it alone."""

    lighting: str | None
    saturation: str | None
    vibration: str | None
    triggers: str | None


class Origami:
    """The plugin backend, independent of Decky.

    Decky starts `start()` as a separate task and may forward frontend calls
    before it finishes, so calls that need the loaded state wait for it.
    """

    def __init__(
        self, environment: Environment, *, emit: Emit, attach_bpf: Attach = HidBpfProgram
    ) -> None:
        self._env = environment
        self._emit = emit
        self._rumble = RumbleProgram(environment.root, environment.plugin_dir / PROGRAM, attach_bpf)
        self._magnifier = Magnifier(environment.root)
        self._settings_store = SettingsStore(environment.settings_dir / "settings.json")
        self._journal = ChangeJournal(environment.data_dir / "changes.json")
        self._settings = Settings()
        self._settings_lock = asyncio.Lock()
        self._controller_lock = asyncio.Lock()
        self._info: Info | None = None
        self._ready = asyncio.Event()
        self._start_error: Exception | None = None
        self._buttons = BackgroundTask("origami-buttons", self._forward_buttons)
        self._buttons_read: frozenset[Button] = frozenset()
        self._after_resume = BackgroundTask("origami-after-resume", self._follow_resumes)
        self._pulsing = False

    async def start(self) -> None:
        try:
            self._settings = await asyncio.to_thread(self._settings_store.load)
            await asyncio.to_thread(self._journal.load)
            device = await asyncio.to_thread(read_device, self._env.root)
            versions = await read_versions(self._env.root, decky=self._env.decky_version)
            self._info = Info(version=self._env.version, device=device, versions=versions)
            log.info("ORIGAMI %s started, board %s", self._env.version, device.board)
        except Exception as error:
            # Surfaced to every frontend call instead of leaving them waiting forever.
            log.exception("ORIGAMI failed to start")
            self._start_error = error
            return
        finally:
            self._ready.set()
        await self._restore_controller()
        await self._restore_gyro()
        await self._follow_settings()

    async def info(self) -> Info:
        await self._started()
        if self._info is None:
            raise RuntimeError("Startup did not produce device information")
        return self._info

    async def telemetry(self) -> Telemetry:
        return await asyncio.to_thread(read_telemetry, self._env.root)

    async def settings(self) -> Settings:
        await self._started()
        return self._settings

    async def update_settings(self, changes: Mapping[str, object]) -> Settings:
        await self._started()
        async with self._settings_lock:
            updated = self._settings.updated(changes)
            if updated == self._settings:
                return self._settings
            # Sent before saving: a change the hardware did not take is not kept.
            if updated.lighting is not None and updated.lighting != self._settings.lighting:
                await self._send_lighting(updated.lighting)
            if updated.saturation is not None and updated.saturation != self._settings.saturation:
                await self._send_saturation(updated.saturation)
            if updated.vibration is not None and updated.vibration != self._settings.vibration:
                await self._send_vibration(updated.vibration)
            triggers_changed = updated.trigger_rumble != self._settings.trigger_rumble
            if triggers_changed or updated.vibration != self._settings.vibration:
                try:
                    await self._send_rumble(updated)
                except (OSError, RuntimeError) as error:
                    # The grips' lift is extra: their strength has reached the MCU already.
                    if triggers_changed:
                        raise
                    log.warning("Grips not lifted: %s", error)
            if updated.gyro_fix != self._settings.gyro_fix:
                await self._set_gyro(on=updated.gyro_fix)
            await asyncio.to_thread(self._settings_store.save, updated)
            self._settings = updated
            await self._follow_settings()
            return self._settings

    async def preview_lighting(self, lighting: Lighting) -> None:
        """Show lighting on the rings without keeping it, while the user picks a colour.

        Applying keeps it through update_settings; cancelling sends the saved lighting back.
        """
        await self._started()
        await self._send_lighting(lighting)

    async def gyro(self) -> GyroState:
        """Whether the gyroscope's axes need ORIGAMI here, and what ORIGAMI has done about them."""
        info = await self.info()
        return await asyncio.to_thread(read_gyro_state, self._env.root, info.device.board)

    async def trigger_state(self) -> TriggerState:
        """Whether the triggers here have motors ORIGAMI can rumble."""
        info = await self.info()
        return await asyncio.to_thread(read_trigger_state, self._env.root, info.device.board)

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

    async def test_trigger_rumble(self) -> None:
        """Rumble the triggers for a second at their level, as a game's full rumble would."""
        await self._started()
        trigger_rumble = self._settings.trigger_rumble
        if self._pulsing or trigger_rumble is None or not trigger_rumble.enabled:
            return
        self._pulsing = True
        try:
            await asyncio.to_thread(start_trigger_pulse, self._env.root, trigger_rumble)
            await asyncio.sleep(PULSE_SECONDS)
        finally:
            self._end_pulse()

    async def saturation(self) -> int | None:
        """The saturation gamescope shows now, ORIGAMI's or not; None without gamescope."""
        return await read_saturation(self._env.root)

    async def restore_saturation(self) -> None:
        """Send the saved saturation again; the frontend calls it whenever Steam's interface loads.

        gamescope forgets the property when it restarts, Steam sets its own value as it starts, and
        within a tenth of a second of every resume the property is back at sRGB (watched on the
        console), so it is also sent after each resume.
        """
        await self._started()
        saturation = self._settings.saturation
        if saturation is None:
            return
        try:
            await self._send_saturation(saturation)
        except (CommandError, OSError, RuntimeError, TimeoutError) as error:
            log.warning("Saturation not restored: %s", error)

    async def changes(self) -> list[Change]:
        await self._started()
        return self._journal.entries()

    async def conflicts(self) -> Conflicts:
        enabled = await asyncio.to_thread(enabled_plugins, self._env.decky_home)

        def owner(names: tuple[str, ...]) -> str | None:
            return next((name for name in names if name in enabled), None)

        return Conflicts(
            lighting=owner(LIGHTING_OWNERS),
            saturation=owner(SATURATION_OWNERS),
            vibration=owner(VIBRATION_OWNERS),
            triggers=owner(TRIGGER_OWNERS),
        )

    def uninstall(self) -> None:
        """Give the system back as it was, when Decky removes the plugin; the settings stay.

        Decky also removes and installs the plugin to update it. Nothing here may wait (see stop),
        so InputPlumber is not restarted: it takes the stock axes when it starts next.
        """
        if remove_fix(self._env.root):
            self._journal.forget("gamepad", "gyro")
        log.info("ORIGAMI uninstalled")

    def stop(self) -> None:
        """Cancel background work before Decky unloads the plugin, without waiting for it.

        Decky ends the process right after unloading, and while the unload waits, Decky 3.3.0's
        own socket listener spins on the closed socket and freezes the event loop, so a waiting
        unload never returns and Decky kills the plugin after 5 s. A vibration test still running
        is stopped right away, the rumble program leaves the controller, and the magnifier goes
        off with the right stick given back to the game.
        """
        self._buttons.cancel()
        self._after_resume.cancel()
        self._end_pulse()
        self._rumble.close()
        try:
            self._magnifier.close()
        except (CommandError, TimeoutError) as error:
            log.warning("Magnifier not switched off: %s", error)
        log.info("ORIGAMI stopped")

    def _start_handle_pulse(self) -> None:
        self._rumble.mute_triggers()
        start_pulse(self._env.root)

    def _end_pulse(self) -> None:
        # Sent at once, without awaiting: an await could be cut short and leave the motors running.
        if not self._pulsing:
            return
        self._pulsing = False
        try:
            stop_rumble(self._env.root)
        except OSError as error:
            log.warning("Vibration test not stopped: %s", error)

    async def _follow_settings(self) -> None:
        settings = self._settings
        buttons = _driven_buttons(settings)
        if buttons != self._buttons_read:
            # The reader opens only the interfaces its buttons come from.
            await self._buttons.stop()
            self._buttons_read = buttons
        await self._buttons.run_while(on=bool(buttons))
        # The controller forgets ORIGAMI's lighting and vibration in sleep, and may come back as
        # new devices without the rumble program; the saturation goes back to Steam's on resume.
        await self._after_resume.run_while(
            on=settings.lighting is not None
            or settings.vibration is not None
            or settings.trigger_rumble is not None
            or settings.saturation is not None
        )

    async def _send_lighting(self, lighting: Lighting) -> None:
        owner = (await self.conflicts()).lighting
        if owner is not None:
            raise RuntimeError(f"{owner} drives the stick lighting, so ORIGAMI leaves it alone")
        async with self._controller_lock:
            await asyncio.to_thread(self._record_lighting)
            await asyncio.to_thread(apply_lighting, self._env.root, lighting)

    async def _send_saturation(self, percent: int) -> None:
        owner = (await self.conflicts()).saturation
        if owner is not None:
            raise RuntimeError(f"{owner} sets the screen colour, so ORIGAMI leaves it alone")
        if not self._journal.recorded("display", "saturation"):
            original = await read_saturation(self._env.root)
            await asyncio.to_thread(self._journal.record, "display", "saturation", original)
        await write_saturation(self._env.root, percent)

    async def _send_vibration(self, vibration: Vibration) -> None:
        owner = (await self.conflicts()).vibration
        if owner is not None:
            raise RuntimeError(f"{owner} sets the vibration strength, so ORIGAMI leaves it alone")
        async with self._controller_lock:
            await asyncio.to_thread(self._record_vibration)
            await asyncio.to_thread(apply_vibration, self._env.root, vibration)

    async def _send_rumble(self, settings: Settings) -> None:
        """Have the rumble program fill the triggers as chosen and lift the grips ORIGAMI drives.

        The grips are lifted only under ORIGAMI's own strength: with another plugin setting it, or
        before the user sets one, games rumble the grips as before.
        """
        owners = await self.conflicts()
        trigger_rumble = settings.trigger_rumble or TriggerRumble()
        own_grips = (
            settings.vibration is not None
            and settings.vibration.enabled
            and owners.vibration is None
        )
        rumble = RumbleSettings(
            *trigger_rumble.strengths(), grips=GRIP_AT_GAME_FULL if own_grips else 0
        )
        async with self._controller_lock:
            if owners.triggers is not None and trigger_rumble.enabled:
                await asyncio.to_thread(self._rumble.close)
                raise RuntimeError(
                    f"{owners.triggers} rumbles the triggers, so ORIGAMI leaves them alone"
                )
            await asyncio.to_thread(self._rumble.apply, rumble)

    def _record_lighting(self) -> None:
        # The controller cannot report its lighting, so the original is its own animation (None).
        self._journal.record("lighting", "rings", None)

    def _record_vibration(self) -> None:
        if self._journal.recorded("gamepad", "vibration"):
            return
        # The MCU cannot be asked, so the original is what the driver last took.
        strength = read_driver_strength(self._env.root)
        self._journal.record("gamepad", "vibration", None if strength is None else list(strength))

    async def _restore_controller(self) -> None:
        """Send the saved lighting, vibration and rumble program again, at start and after sleep.

        Failures are only logged: the controller may be gone, or another plugin drives it now.
        """
        lighting, vibration = self._settings.lighting, self._settings.vibration
        if lighting is not None:
            try:
                await self._send_lighting(lighting)
            except (OSError, RuntimeError) as error:
                log.warning("Lighting not restored: %s", error)
        if vibration is not None:
            try:
                await self._send_vibration(vibration)
            except (OSError, RuntimeError) as error:
                log.warning("Vibration not restored: %s", error)
        if vibration is not None or self._settings.trigger_rumble is not None:
            try:
                await self._send_rumble(self._settings)
            except (OSError, RuntimeError) as error:
                log.warning("Rumble program not restored: %s", error)

    async def _follow_resumes(self) -> None:
        async with aclosing(resumes()) as wakes:
            async for _ in wakes:
                await asyncio.sleep(RESUME_SETTLE_SECONDS)
                await self._restore_controller()
                await self.restore_saturation()

    async def _set_gyro(self, *, on: bool) -> None:
        """Make the gyroscope's axes follow the setting; InputPlumber restarts for a new file."""
        state = await self.gyro()
        match on, state:
            case True, GyroState.WRONG | GyroState.OUTDATED:
                await asyncio.to_thread(self._journal.record, "gamepad", "gyro", None)
                await asyncio.to_thread(write_fix, self._env.root)
            case False, GyroState.FIXED | GyroState.OUTDATED:
                await asyncio.to_thread(remove_fix, self._env.root)
                await asyncio.to_thread(self._journal.forget, "gamepad", "gyro")
            case True, GyroState.FIXED:
                return
            case True, _:
                raise RuntimeError(f"ORIGAMI cannot fix the gyroscope here ({state})")
            case _:
                return
        await restart_inputplumber()

    async def _restore_gyro(self) -> None:
        """Keep the axes as set: InputPlumber may have been updated, or the file may be gone."""
        try:
            await self._set_gyro(on=self._settings.gyro_fix)
        except (CommandError, OSError, RuntimeError, TimeoutError) as error:
            log.warning("Gyroscope not restored: %s", error)

    async def _forward_buttons(self) -> None:
        async with aclosing(button_presses(self._env.root, self._buttons_read)) as presses:
            async for button in presses:
                match button:
                    case Button.QUICK_ACCESS:
                        # Steam misses some presses while a game runs (B16). The frontend sees
                        # whether Steam registered this one and opens the menu itself if not.
                        await self._emit(QAM_PRESSED)
                    case Button.ARMOURY_CRATE:
                        await self._act(self._settings.armoury_crate)
                    case Button.ARMOURY_CRATE_HOLD:
                        await self._act(self._settings.armoury_crate_hold)

    async def _act(self, action: ButtonAction) -> None:
        """Do what the backend can do itself; have the frontend do the rest in Steam's interface."""
        chord = CHORDS.get(action)
        try:
            if chord is not None:
                await asyncio.to_thread(press_chord, self._env.root, chord)
            elif action is ButtonAction.MAGNIFIER:
                await asyncio.to_thread(self._magnifier.toggle)
            elif action is not ButtonAction.NONE:
                await self._emit(BUTTON_ACTION, action.value)
        except (CommandError, TimeoutError, ValueError) as error:
            log.warning("%s not done: %s", action.value, error)

    async def _started(self) -> None:
        await self._ready.wait()
        if self._start_error is not None:
            raise RuntimeError("ORIGAMI failed to start, see the plugin log") from self._start_error


def _driven_buttons(settings: Settings) -> frozenset[Button]:
    """The buttons whose presses ORIGAMI needs with these settings."""
    driven = {
        Button.QUICK_ACCESS: settings.qam_assist,
        Button.ARMOURY_CRATE: settings.armoury_crate is not ButtonAction.NONE,
        Button.ARMOURY_CRATE_HOLD: settings.armoury_crate_hold is not ButtonAction.NONE,
    }
    return frozenset(button for button, needed in driven.items() if needed)
