# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from contextlib import aclosing
from dataclasses import dataclass
from pathlib import Path

from origami.buttons import Button, button_presses
from origami.decky_plugins import (
    LIGHTING_OWNERS,
    SATURATION_OWNERS,
    VIBRATION_OWNERS,
    enabled_plugins,
)
from origami.device import Device, read_device
from origami.journal import Change, ChangeJournal
from origami.lighting import Lighting, apply_lighting
from origami.power import resumes
from origami.proc import CommandError
from origami.saturation import read_saturation, write_saturation
from origami.settings import Settings, SettingsStore
from origami.tasks import BackgroundTask
from origami.telemetry import Telemetry, read_telemetry
from origami.versions import Versions, read_versions
from origami.vibration import (
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

RESUME_SETTLE_SECONDS = 2.0
"""The driver resets the controller on resume; ORIGAMI sends its settings after that."""

Emit = Callable[[str], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class Environment:
    """Where the backend runs: the filesystem root, Decky's folders and the versions."""

    root: Path
    settings_dir: Path
    data_dir: Path
    decky_home: Path
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


class Origami:
    """The plugin backend, independent of Decky.

    Decky starts `start()` as a separate task and may forward frontend calls
    before it finishes, so calls that need the loaded state wait for it.
    """

    def __init__(self, environment: Environment, *, emit: Emit) -> None:
        self._env = environment
        self._emit = emit
        self._settings_store = SettingsStore(environment.settings_dir / "settings.json")
        self._journal = ChangeJournal(environment.data_dir / "changes.json")
        self._settings = Settings()
        self._settings_lock = asyncio.Lock()
        self._controller_lock = asyncio.Lock()
        self._info: Info | None = None
        self._ready = asyncio.Event()
        self._start_error: Exception | None = None
        self._qam_assist = BackgroundTask("origami-qam-assist", self._forward_quick_access)
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

    async def test_vibration(self) -> None:
        """Rumble the handles for a second, so the strength can be felt without a game.

        The controller keeps a rumble until it is told to stop, so the pulse always ends with a
        stop, also when the call is cancelled or the plugin unloads. A press during it is ignored.
        """
        if self._pulsing:
            return
        self._pulsing = True
        try:
            await asyncio.to_thread(start_pulse, self._env.root)
            await asyncio.sleep(PULSE_SECONDS)
        finally:
            self._end_pulse()

    async def saturation(self) -> int | None:
        """The saturation gamescope shows now, ORIGAMI's or not; None without gamescope."""
        return await read_saturation(self._env.root)

    async def restore_saturation(self) -> None:
        """Send the saved saturation again; the frontend calls it whenever Steam's interface loads.

        gamescope forgets the property when it restarts, and Steam sets its own value as it starts.
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
        )

    def stop(self) -> None:
        """Cancel background work before Decky unloads the plugin, without waiting for it.

        Decky ends the process right after unloading, and while the unload waits, Decky 3.3.0's
        own socket listener spins on the closed socket and freezes the event loop, so a waiting
        unload never returns and Decky kills the plugin after 5 s. A vibration test still running
        is stopped right away.
        """
        self._qam_assist.cancel()
        self._after_resume.cancel()
        self._end_pulse()
        log.info("ORIGAMI stopped")

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
        await self._qam_assist.run_while(on=settings.qam_assist)
        # The controller forgets ORIGAMI's lighting and vibration in sleep.
        await self._after_resume.run_while(
            on=settings.lighting is not None or settings.vibration is not None
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
        """Send the saved lighting and vibration again, at start and after sleep.

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

    async def _follow_resumes(self) -> None:
        async with aclosing(resumes()) as wakes:
            async for _ in wakes:
                await asyncio.sleep(RESUME_SETTLE_SECONDS)
                await self._restore_controller()

    async def _forward_quick_access(self) -> None:
        # Steam misses some presses while a game runs (B16). The frontend sees whether Steam
        # registered this one and opens the menu itself if it did not.
        async with aclosing(button_presses(self._env.root)) as presses:
            async for button in presses:
                if button is Button.QUICK_ACCESS:
                    await self._emit(QAM_PRESSED)

    async def _started(self) -> None:
        await self._ready.wait()
        if self._start_error is not None:
            raise RuntimeError("ORIGAMI failed to start, see the plugin log") from self._start_error
