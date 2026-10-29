# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import logging
from collections.abc import Awaitable, Mapping
from contextlib import aclosing, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from origami.buttons import Button, ButtonAction, button_presses
from origami.cpu import program_cap, read_boost, write_boost
from origami.decky_plugins import (
    FAN_OWNERS,
    LIGHTING_OWNERS,
    POWER_OWNERS,
    SATURATION_OWNERS,
    TRIGGER_OWNERS,
    VIBRATION_OWNERS,
    enabled_plugins,
)
from origami.device import Device, read_device
from origami.fans import POLL_SECONDS as FAN_POLL_SECONDS
from origami.fans import FanCurve, curve_dir, curve_on, give_back, write_curve
from origami.gyro import GyroState, read_gyro_state, remove_fix, restart_inputplumber, write_fix
from origami.hid_bpf import HidBpfProgram
from origami.inputplumber import Chord, press_chord
from origami.journal import Change, ChangeJournal
from origami.jsonio import JsonValue
from origami.lighting import CONTROLLER_LIGHTING, Lighting, apply_lighting
from origami.magnifier import Magnifier
from origami.power import POLL_SECONDS, HeldPower, PowerKeeper, PowerTarget, resumes
from origami.proc import CommandError
from origami.rumble import PROGRAM, Attach, RumbleProgram, RumbleSettings
from origami.saturation import read_saturation, write_saturation
from origami.settings import Settings, SettingsStore
from origami.tasks import BackgroundTask
from origami.tdp import read_limits, reset_to_profile
from origami.telemetry import Telemetry, read_telemetry
from origami.triggers import (
    TAP_GAP_SECONDS,
    TAP_SECONDS,
    TAPS_IN_TEST,
    TriggerRumble,
    TriggerState,
    read_trigger_state,
    start_trigger_pulse,
)
from origami.uevents import supply_changes
from origami.versions import Versions, read_versions
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

GIVEN_BACK = frozenset(
    {
        ("power", "tdp"),
        ("power", "cpu_boost"),
        ("fans", "curve"),
        ("display", "saturation"),
        ("lighting", "rings"),
        ("gamepad", "vibration"),
        ("gamepad", "gyro"),
    }
)
"""Journal entries ORIGAMI knows how to give back; others, left by older versions, are forgotten."""


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
    power: str | None
    fans: str | None


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
        self._keeper = PowerKeeper(environment.root)
        self._steam_tdp_limit = False
        self._game: int | None = None
        """The game Steam runs now, whose own power applies while it has an active profile."""
        self._look_now = asyncio.Event()
        """Wakes the keeper before its next look: a supply changed, or there is news to write."""
        self._power = BackgroundTask("origami-power", self._hold_power)
        self._fans = BackgroundTask("origami-fans", self._hold_fans)
        self._fans_written: tuple[int, ...] | None = None
        """The points last sent to the fans while ORIGAMI holds them."""
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
            if _power_changed(self._settings, updated):
                owner = (await self.conflicts()).power
                if owner is not None:
                    raise RuntimeError(f"{owner} sets the power, so ORIGAMI leaves it alone")
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
            if updated.fans != self._settings.fans:
                await self._send_fans(updated.fans)
            # Unset and off are the same axes: switching off a fix never set changes nothing.
            if bool(updated.gyro_fix) != bool(self._settings.gyro_fix):
                await self._set_gyro(on=bool(updated.gyro_fix))
            await asyncio.to_thread(self._settings_store.save, updated)
            gave_up_tdp = self._settings.manage_tdp is True and updated.manage_tdp is not True
            self._settings = updated
            await self._follow_settings()
            if gave_up_tdp:
                await asyncio.to_thread(self._give_back_tdp)
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
        """Rumble the triggers at their level as a game's full rumble would: a second, or taps."""
        await self._started()
        trigger_rumble = self._settings.trigger_rumble
        if self._pulsing or trigger_rumble is None or not trigger_rumble.enabled:
            return
        self._pulsing = True
        try:
            if trigger_rumble.taps:
                # Taps as a game's shots give them, not one long rumble.
                # The last tap ends with the test.
                for tap in range(TAPS_IN_TEST):
                    if tap:
                        await asyncio.to_thread(stop_rumble, self._env.root)
                        await asyncio.sleep(TAP_GAP_SECONDS)
                    await asyncio.to_thread(start_trigger_pulse, self._env.root, trigger_rumble)
                    await asyncio.sleep(TAP_SECONDS)
            else:
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

    async def power(self) -> HeldPower:
        """The limits ORIGAMI holds now, for the Power screen."""
        return self._keeper.held()

    async def set_steam_tdp_limit(self, *, on: bool) -> None:
        """Steam's TDP slider was switched on or off (in the performance profile, where it works).

        While ORIGAMI manages the TDP, it keeps it: the slider's writes are answered at once, and
        the Power screen says the slider does nothing. Steam sets the TDP once "Manage TDP" is off.
        """
        await self._started()
        if on != self._steam_tdp_limit:
            self._steam_tdp_limit = on
            log.info("Steam's TDP slider is %s", "on: ORIGAMI writes over it" if on else "off")
            await self._follow_power(self._settings)

    async def set_game(self, app_id: int | None) -> None:
        """Steam runs this game now, or none: the power follows the game's own profile, if any."""
        await self._started()
        if app_id != self._game:
            self._game = app_id
            own = self._settings.power_for(app_id) is not self._settings.power
            log.info(
                "Running game: %s, power: %s",
                app_id or "none",
                "its own profile" if own else "general",
            )
            await self._follow_power(self._settings)

    async def game_started(self) -> None:
        """Steam started a game: it writes its own limits meanwhile, so ORIGAMI writes again."""
        self._keeper.game_started()
        self._look_now.set()

    async def changes(self) -> list[Change]:
        await self._started()
        return self._journal.entries()

    async def conflicts(self) -> Conflicts:
        return await asyncio.to_thread(self._read_conflicts)

    async def restore_all(self) -> Settings:
        """Give the system back as it was before ORIGAMI, as uninstalling does, and keep running.

        The settings drop all ORIGAMI drives (Settings.restored), so nothing comes back; its file
        goes and InputPlumber restarts with the stock axes. What could not be given back stays in
        the journal, so the screen still lists it.
        """
        await self._started()
        async with self._settings_lock:
            restored = self._settings.restored()
            await asyncio.to_thread(self._settings_store.save, restored)
            self._settings = restored
            # The keeper leaves the TDP and the boost from now on, and the fans go back.
            await self._follow_settings()
            await asyncio.to_thread(self._rumble.close)
            await asyncio.to_thread(self._give_back_tdp)
            await asyncio.to_thread(self._give_back_boost)
            owners = await self.conflicts()
            async with self._controller_lock:
                await asyncio.to_thread(self._give_back_controller, owners)
            await self._give_back_saturation(owners.saturation)
            try:
                await self._set_gyro(on=False)
            except (CommandError, OSError, RuntimeError, TimeoutError) as error:
                log.warning("Gyroscope not given back: %s", error)
            for change in self._journal.entries():
                if (change.module, change.key) not in GIVEN_BACK:
                    log.info("Forgetting %s.%s: nothing gives it back", change.module, change.key)
                    await asyncio.to_thread(self._journal.forget, change.module, change.key)
            log.info("Everything given back, %d changes left", len(self._journal.entries()))
            return self._settings

    def _read_conflicts(self) -> Conflicts:
        enabled = enabled_plugins(self._env.decky_home)

        def owner(names: tuple[str, ...]) -> str | None:
            return next((name for name in names if name in enabled), None)

        return Conflicts(
            lighting=owner(LIGHTING_OWNERS),
            saturation=owner(SATURATION_OWNERS),
            vibration=owner(VIBRATION_OWNERS),
            triggers=owner(TRIGGER_OWNERS),
            power=owner(POWER_OWNERS),
            fans=owner(FAN_OWNERS),
        )

    def uninstall(self) -> None:
        """Give the system back as it was, when Decky removes the plugin; the settings stay.

        Decky also removes and installs the plugin to update it. Nothing here may wait (see stop),
        so InputPlumber is not restarted: it takes the stock axes when it starts next. The firmware
        gets its platform profile's own power back, and the CPU boost what it was before ORIGAMI.
        """
        if remove_fix(self._env.root):
            self._journal.forget("gamepad", "gyro")
        self._give_back_fans()
        self._give_back_tdp()
        self._give_back_boost()
        self._give_back_controller(self._read_conflicts())
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
        self._power.cancel()
        self._fans.cancel()
        # A look at the hardware still running in its thread ends before this returns.
        self._keeper.hold(None)
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
        await self._follow_power(settings)
        await self._follow_fans(settings)
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

    async def _follow_power(self, settings: Settings) -> None:
        """Hold the power as set, unless another plugin owns it; the journal remembers first."""
        if (await self.conflicts()).power is not None:
            target = None
        else:
            target = PowerTarget(
                settings.power_for(self._game),
                tdp=settings.manage_tdp is True,
                battery_high_tdp=settings.battery_high_tdp,
                steam_slider=self._steam_tdp_limit,
            )
            await asyncio.to_thread(self._record_power, target)
        self._keeper.hold(target)
        self._look_now.set()
        await self._power.run_while(on=target is not None)

    def _record_power(self, target: PowerTarget) -> None:
        if target.tdp and read_limits(self._env.root) is not None:
            # The firmware's power before ORIGAMI is its platform profile's own, not a value.
            self._journal.record("power", "tdp", None)
        if target.power.cpu_boost is not None and not self._journal.recorded("power", "cpu_boost"):
            self._journal.record("power", "cpu_boost", read_boost(self._env.root))

    def _give_back_tdp(self) -> None:
        """Let the firmware run its platform profile's own power again; blocks briefly."""
        if not self._journal.recorded("power", "tdp"):
            return
        try:
            reset_to_profile(self._env.root)
        except OSError as error:
            log.warning("TDP not given back to the platform profile: %s", error)
            return
        self._journal.forget("power", "tdp")
        log.info("TDP given back to the platform profile")

    async def _send_fans(self, curve: FanCurve | None) -> None:
        """Send a changed curve before it is saved, so a curve the firmware refused is not kept."""
        if (
            curve is None
            or not curve.enabled
            or await asyncio.to_thread(curve_dir, self._env.root) is None
        ):
            return
        owner = (await self.conflicts()).fans
        if owner is not None:
            raise RuntimeError(f"{owner} sets the fans, so ORIGAMI leaves them alone")
        await asyncio.to_thread(self._write_fans, curve.points)

    async def _follow_fans(self, settings: Settings) -> None:
        """Hold the fan curve while it is on and no plugin drives the fans; else give them back."""
        curve = settings.fans
        hold = (
            curve is not None
            and curve.enabled
            and await asyncio.to_thread(curve_dir, self._env.root) is not None
            and (await self.conflicts()).fans is None
        )
        if curve is not None and hold:
            if curve.points != self._fans_written or not await asyncio.to_thread(
                curve_on, self._env.root
            ):
                try:
                    await asyncio.to_thread(self._write_fans, curve.points)
                except OSError as error:
                    log.warning("Fan curve not written: %s", error)
        elif self._journal.recorded("fans", "curve"):
            await asyncio.to_thread(self._give_back_fans)
        await self._fans.run_while(on=hold)

    def _write_fans(self, points: tuple[int, ...]) -> None:
        """Send the curve to the fans, the journal remembering first; blocks briefly."""
        if not self._journal.recorded("fans", "curve"):
            # The fans ran the firmware's own curve before ORIGAMI, not a value.
            self._journal.record("fans", "curve", None)
        write_curve(self._env.root, points)
        self._fans_written = points
        log.info("Fan curve written: %s", "/".join(map(str, points)))

    async def _hold_fans(self) -> None:
        """Switch the curve on again whenever something switches it off: a platform profile, say."""
        while True:
            await asyncio.sleep(FAN_POLL_SECONDS)
            curve = self._settings.fans
            if (
                curve is None
                or not curve.enabled
                or await asyncio.to_thread(curve_on, self._env.root)
            ):
                continue
            try:
                await asyncio.to_thread(write_curve, self._env.root, curve.points)
                log.info("Fan curve switched on again")
            except OSError as error:
                log.warning("Fan curve not switched on again: %s", error)

    def _give_back_fans(self) -> None:
        """Let the firmware run the fans on its own curve again; blocks briefly."""
        if not self._journal.recorded("fans", "curve"):
            return
        try:
            give_back(self._env.root)
        except OSError as error:
            log.warning("Fans not given back to the firmware: %s", error)
            return
        self._journal.forget("fans", "curve")
        self._fans_written = None
        # The firmware's own curve may bring back the profile's own power: the limits go again.
        self._keeper.write_again("fans given back")
        self._look_now.set()
        log.info("Fans given back to the firmware")

    def _give_back_controller(self, owners: Conflicts) -> None:
        """The rings and the handles' strength as they were before ORIGAMI; blocks briefly.

        A plugin that drives them now keeps them as it set them: only ORIGAMI's record goes.
        """
        if self._journal.recorded("lighting", "rings"):
            try:
                if owners.lighting is None:
                    apply_lighting(self._env.root, CONTROLLER_LIGHTING)
                self._journal.forget("lighting", "rings")
            except OSError as error:
                log.warning("Lighting not given back: %s", error)
        if self._journal.recorded("gamepad", "vibration"):
            original = original_vibration(self._journal.original("gamepad", "vibration"))
            try:
                if owners.vibration is None:
                    apply_vibration(self._env.root, original)
                self._journal.forget("gamepad", "vibration")
            except OSError as error:
                log.warning("Vibration strength not given back: %s", error)

    async def _give_back_saturation(self, owner: str | None) -> None:
        """Gamescope's saturation as it was before ORIGAMI, unless a plugin sets it now."""
        if not self._journal.recorded("display", "saturation"):
            return
        original = self._journal.original("display", "saturation")
        if owner is None and isinstance(original, int) and not isinstance(original, bool):
            try:
                await write_saturation(self._env.root, original)
            except (CommandError, OSError, TimeoutError) as error:
                log.warning("Saturation not given back: %s", error)
                return
        await asyncio.to_thread(self._journal.forget, "display", "saturation")

    def _give_back_boost(self) -> None:
        original = self._journal.original("power", "cpu_boost")
        if isinstance(original, bool):
            try:
                write_boost(self._env.root, on=original)
            except OSError as error:
                log.warning("CPU boost not given back: %s", error)
                return
        self._journal.forget("power", "cpu_boost")

    async def _hold_power(self) -> None:
        """Let the keeper look when it asks to, and at once when something changes."""
        watcher = asyncio.create_task(self._watch_supplies())
        try:
            while True:
                # Cleared before the look: a change meanwhile brings the next one at once.
                self._look_now.clear()
                cap_due = await asyncio.to_thread(self._keeper.tick)
                if cap_due is not None:
                    try:
                        await program_cap(self._env.root)
                        log.info("CPU frequency cap programmed again: %s", cap_due)
                    except OSError as error:
                        log.warning("CPU frequency cap not programmed: %s", error)
                with suppress(TimeoutError):
                    async with asyncio.timeout(self._keeper.next_look()):
                        await self._look_now.wait()
        finally:
            watcher.cancel()

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
            await self._set_gyro(on=bool(self._settings.gyro_fix))
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
                        await self._act(self._settings.armoury_crate or ButtonAction.NONE)
                    case Button.ARMOURY_CRATE_HOLD:
                        await self._act(self._settings.armoury_crate_hold or ButtonAction.NONE)

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


def _power_changed(before: Settings, after: Settings) -> bool:
    return (before.power, before.battery_high_tdp, before.game_power) != (
        after.power,
        after.battery_high_tdp,
        after.game_power,
    )


def _driven_buttons(settings: Settings) -> frozenset[Button]:
    """The buttons whose presses ORIGAMI needs with these settings."""
    driven = {
        Button.QUICK_ACCESS: settings.qam_assist is True,
        Button.ARMOURY_CRATE: settings.armoury_crate not in {None, ButtonAction.NONE},
        Button.ARMOURY_CRATE_HOLD: settings.armoury_crate_hold not in {None, ButtonAction.NONE},
    }
    return frozenset(button for button, needed in driven.items() if needed)
