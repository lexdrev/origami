# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""Decky entry point: a thin adapter over the backend in py_modules/origami."""

from pathlib import Path
from typing import cast

import decky

from origami.app import Origami
from origami.jsonio import JsonValue
from origami.wire import to_wire


class Plugin:
    def __init__(self) -> None:
        self._app = Origami(
            root=Path("/"),
            settings_dir=Path(decky.DECKY_PLUGIN_SETTINGS_DIR),
            data_dir=Path(decky.DECKY_PLUGIN_RUNTIME_DIR),
            version=decky.DECKY_PLUGIN_VERSION,
            decky_version=decky.DECKY_VERSION or None,
        )

    async def _main(self) -> None:
        await self._app.start()

    async def get_info(self) -> JsonValue:
        return to_wire(await self._app.info())

    async def get_telemetry(self) -> JsonValue:
        return to_wire(await self._app.telemetry())

    async def get_settings(self) -> JsonValue:
        return to_wire(await self._app.settings())

    async def update_settings(self, changes: object) -> JsonValue:
        if not isinstance(changes, dict):
            raise TypeError("Settings changes must be an object")
        return to_wire(await self._app.update_settings(cast("dict[str, object]", changes)))

    async def get_changes(self) -> JsonValue:
        return to_wire(await self._app.changes())
