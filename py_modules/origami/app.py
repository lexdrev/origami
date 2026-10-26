# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from contextlib import aclosing
from dataclasses import dataclass
from pathlib import Path

from origami.buttons import Button, button_presses
from origami.decky_plugins import LIGHTING_OWNERS, enabled_plugins
from origami.device import Device, read_device
from origami.journal import Change, ChangeJournal
from origami.lighting import Lighting, apply_lighting
from origami.power import resumes
from origami.settings import Settings, SettingsStore
from origami.tasks import BackgroundTask
from origami.telemetry import Telemetry, read_telemetry
from origami.versions import Versions, read_versions

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
        self._lighting_lock = asyncio.Lock()
        self._info: Info | None = None
        self._ready = asyncio.Event()
        self._start_error: Exception | None = None
        self._qam_assist = BackgroundTask("origami-qam-assist", self._forward_quick_access)
        self._after_resume = BackgroundTask("origami-after-resume", self._follow_resumes)

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
        await self._restore_lighting()
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
            if updated.lighting is not None and updated.lighting != self._settings.lighting:
                # Sent before saving: lighting the controller did not take is not kept.
                await self._send_lighting(updated.lighting)
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

    async def changes(self) -> list[Change]:
        await self._started()
        return self._journal.entries()

    async def conflicts(self) -> Conflicts:
        enabled = await asyncio.to_thread(enabled_plugins, self._env.decky_home)
        return Conflicts(lighting=next((name for name in LIGHTING_OWNERS if name in enabled), None))

    def stop(self) -> None:
        """Cancel background work before Decky unloads the plugin, without waiting for it.

        Decky ends the process right after unloading, and while the unload waits, Decky 3.3.0's
        own socket listener spins on the closed socket and freezes the event loop, so a waiting
        unload never returns and Decky kills the plugin after 5 s.
        """
        self._qam_assist.cancel()
        self._after_resume.cancel()
        log.info("ORIGAMI stopped")

    async def _follow_settings(self) -> None:
        await self._qam_assist.run_while(on=self._settings.qam_assist)
        await self._after_resume.run_while(on=self._settings.lighting is not None)

    async def _send_lighting(self, lighting: Lighting) -> None:
        owner = (await self.conflicts()).lighting
        if owner is not None:
            raise RuntimeError(f"{owner} drives the stick lighting, so ORIGAMI leaves it alone")
        async with self._lighting_lock:
            await asyncio.to_thread(self._record_lighting)
            await asyncio.to_thread(apply_lighting, self._env.root, lighting)

    def _record_lighting(self) -> None:
        # The controller cannot report its lighting, so the original is its own animation (None).
        self._journal.record("lighting", "rings", None)

    async def _restore_lighting(self) -> None:
        """Send the saved lighting again, at start and after sleep; failures are only logged."""
        lighting = self._settings.lighting
        if lighting is None:
            return
        try:
            await self._send_lighting(lighting)
        except (OSError, RuntimeError) as error:
            log.warning("Lighting not restored: %s", error)

    async def _follow_resumes(self) -> None:
        async with aclosing(resumes()) as wakes:
            async for _ in wakes:
                await asyncio.sleep(RESUME_SETTLE_SECONDS)
                await self._restore_lighting()

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
