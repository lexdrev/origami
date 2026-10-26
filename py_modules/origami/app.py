# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from origami.device import Device, read_device
from origami.journal import Change, ChangeJournal
from origami.settings import Settings, SettingsStore
from origami.telemetry import Telemetry, read_telemetry
from origami.versions import Versions, read_versions

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Info:
    version: str
    device: Device
    versions: Versions


class Origami:
    """The plugin backend, independent of Decky.

    Decky starts `start()` as a separate task and may forward frontend calls
    before it finishes, so calls that need the loaded state wait for it.
    """

    def __init__(
        self,
        *,
        root: Path,
        settings_dir: Path,
        data_dir: Path,
        version: str,
        decky_version: str | None,
    ) -> None:
        self._root = root
        self._version = version
        self._decky_version = decky_version
        self._settings_store = SettingsStore(settings_dir / "settings.json")
        self._journal = ChangeJournal(data_dir / "changes.json")
        self._settings = Settings()
        self._settings_lock = asyncio.Lock()
        self._info: Info | None = None
        self._ready = asyncio.Event()
        self._start_error: Exception | None = None

    async def start(self) -> None:
        try:
            self._settings = await asyncio.to_thread(self._settings_store.load)
            await asyncio.to_thread(self._journal.load)
            device = await asyncio.to_thread(read_device, self._root)
            versions = await read_versions(self._root, decky=self._decky_version)
            self._info = Info(version=self._version, device=device, versions=versions)
            log.info("ORIGAMI %s started, board %s", self._version, device.board)
        except Exception as error:
            # Surfaced to every frontend call instead of leaving them waiting forever.
            log.exception("ORIGAMI failed to start")
            self._start_error = error
        finally:
            self._ready.set()

    async def info(self) -> Info:
        await self._started()
        if self._info is None:
            raise RuntimeError("Startup did not produce device information")
        return self._info

    async def telemetry(self) -> Telemetry:
        return await asyncio.to_thread(read_telemetry, self._root)

    async def settings(self) -> Settings:
        await self._started()
        return self._settings

    async def update_settings(self, changes: Mapping[str, object]) -> Settings:
        await self._started()
        async with self._settings_lock:
            updated = self._settings.updated(changes)
            if updated != self._settings:
                await asyncio.to_thread(self._settings_store.save, updated)
                self._settings = updated
            return self._settings

    async def changes(self) -> list[Change]:
        await self._started()
        return self._journal.entries()

    async def _started(self) -> None:
        await self._ready.wait()
        if self._start_error is not None:
            raise RuntimeError("ORIGAMI failed to start, see the plugin log") from self._start_error
