# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""Decky entry point: a thin adapter over the backend in py_modules/origami."""

from pathlib import Path
from typing import cast

import decky

from origami.app import Environment, Origami
from origami.jsonio import JsonValue
from origami.lighting import Lighting
from origami.wire import from_wire, to_wire


class Plugin:
    def __init__(self) -> None:
        environment = Environment(
            root=Path("/"),
            settings_dir=Path(decky.DECKY_PLUGIN_SETTINGS_DIR),
            data_dir=Path(decky.DECKY_PLUGIN_RUNTIME_DIR),
            decky_home=Path(decky.DECKY_HOME),
            plugin_dir=Path(decky.DECKY_PLUGIN_DIR),
            version=decky.DECKY_PLUGIN_VERSION,
            decky_version=decky.DECKY_VERSION or None,
        )
        self._app = Origami(environment, emit=decky.emit)

    async def _main(self) -> None:
        await self._app.start()

    async def _unload(self) -> None:
        # Must not await anything: see Origami.stop.
        self._app.stop()

    async def _uninstall(self) -> None:
        # Runs right after _unload, under the same rule.
        self._app.uninstall()

    async def get_info(self) -> JsonValue:
        return to_wire(await self._app.info())

    async def get_telemetry(self) -> JsonValue:
        return to_wire(await self._app.telemetry())

    async def get_settings(self) -> JsonValue:
        return to_wire(await self._app.settings())

    async def update_settings(self, changes: object) -> JsonValue:
        if not isinstance(changes, dict):
            raise TypeError("Settings changes must be an object")
        settings = await self._app.update_settings(from_wire(cast("dict[str, object]", changes)))
        return to_wire(settings)

    async def preview_lighting(self, lighting: object) -> None:
        if not isinstance(lighting, dict):
            raise TypeError("Lighting must be an object")
        await self._app.preview_lighting(
            Lighting.from_json(from_wire(cast("dict[str, object]", lighting)))
        )

    async def get_gyro(self) -> JsonValue:
        return (await self._app.gyro()).value

    async def get_trigger_state(self) -> JsonValue:
        return (await self._app.trigger_state()).value

    async def test_trigger_rumble(self) -> None:
        await self._app.test_trigger_rumble()

    async def test_vibration(self) -> None:
        await self._app.test_vibration()

    async def get_power(self) -> JsonValue:
        return to_wire(await self._app.power())

    async def game_started(self) -> None:
        await self._app.game_started()

    async def set_steam_tdp_limit(self, on: object) -> None:
        if not isinstance(on, bool):
            raise TypeError("Steam's TDP slider is on or off")
        await self._app.set_steam_tdp_limit(on=on)

    async def set_game(self, app_id: object) -> None:
        if app_id is not None and (
            not isinstance(app_id, int) or isinstance(app_id, bool) or app_id <= 0
        ):
            raise TypeError("The running game is a Steam app id or none")
        await self._app.set_game(app_id)

    async def get_changes(self) -> JsonValue:
        return to_wire(await self._app.changes())

    async def get_saturation(self) -> JsonValue:
        return await self._app.saturation()

    async def restore_saturation(self) -> None:
        await self._app.restore_saturation()

    async def get_conflicts(self) -> JsonValue:
        return to_wire(await self._app.conflicts())

    async def restore_all(self) -> JsonValue:
        return to_wire(await self._app.restore_all())
