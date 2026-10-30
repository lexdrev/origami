# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""The plugin backend: the settings, the journal of changes, and the blocks that drive hardware."""

import asyncio
import logging
from collections.abc import Mapping
from contextlib import aclosing
from dataclasses import dataclass
from pathlib import Path

from origami.blocks import Context, Emit
from origami.blocks.buttons import ButtonsBlock
from origami.blocks.display import DisplayBlock
from origami.blocks.fans import FansBlock
from origami.blocks.gamepad import GamepadBlock
from origami.blocks.power import PowerBlock, power_settings_changed
from origami.decky_plugins import Conflicts, read_conflicts
from origami.device import Device, read_device
from origami.gyro import GyroState
from origami.hid_bpf import HidBpfProgram
from origami.journal import Change, ChangeJournal
from origami.lighting import Lighting
from origami.power import HeldPower, resumes
from origami.proc import CommandError
from origami.rumble import PROGRAM, Attach
from origami.settings import Settings, SettingsStore
from origami.tasks import BackgroundTask
from origami.telemetry import Telemetry, read_telemetry
from origami.triggers import TriggerState
from origami.versions import Versions, read_versions

log = logging.getLogger(__name__)

RESUME_SETTLE_SECONDS = 2.0
"""The driver resets the controller on resume; ORIGAMI sends its settings after that."""


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


class Origami:
    """The plugin backend, independent of Decky: it keeps the settings and calls the blocks.

    Every tile has its block in origami.blocks, and the buttons have one too. A change goes to the
    blocks before the settings keep it, so a change the hardware did not take is not kept.

    Decky starts `start()` as a separate task and may forward frontend calls
    before it finishes, so calls that need the loaded state wait for it.
    """

    def __init__(
        self, environment: Environment, *, emit: Emit, attach_bpf: Attach = HidBpfProgram
    ) -> None:
        self._env = environment
        self._settings_store = SettingsStore(environment.settings_dir / "settings.json")
        self._journal = ChangeJournal(environment.data_dir / "changes.json")
        context = Context(environment.root, self._journal, self.conflicts)
        self._settings = Settings()
        self._settings_lock = asyncio.Lock()
        self._controller_lock = asyncio.Lock()
        """Taken around every report to the controller's MCU, by the display and gamepad blocks."""
        self._info: Info | None = None
        self._ready = asyncio.Event()
        self._start_error: Exception | None = None
        self._after_resume = BackgroundTask("origami-after-resume", self._follow_resumes)
        self._power = PowerBlock(context)
        self._fans = FansBlock(context, limits_again=self._power.write_again, look=self._power.look)
        self._display = DisplayBlock(context, self._controller_lock)
        self._gamepad = GamepadBlock(
            context,
            self._controller_lock,
            program=environment.plugin_dir / PROGRAM,
            attach_bpf=attach_bpf,
            board=self._board,
        )
        self._buttons = ButtonsBlock(context, emit=emit, board=self._board_now)

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
        # Frontend calls may come in as soon as the settings are loaded: they wait for these.
        async with self._settings_lock:
            await self._restore_controller()
            await self._gamepad.restore_gyro(self._settings)
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
            if power_settings_changed(self._settings, updated):
                owner = (await self.conflicts()).power
                if owner is not None:
                    raise RuntimeError(f"{owner} sets the power, so ORIGAMI leaves it alone")
            # Sent before saving: a change the hardware did not take is not kept.
            if updated.lighting is not None and updated.lighting != self._settings.lighting:
                await self._display.send_lighting(updated.lighting)
            if updated.saturation is not None and updated.saturation != self._settings.saturation:
                await self._display.send_saturation(updated.saturation)
            await self._gamepad.send(self._settings, updated)
            if updated.fans != self._settings.fans:
                await self._fans.send(updated.fans)
            await self._gamepad.send_gyro(self._settings, updated)
            await asyncio.to_thread(self._settings_store.save, updated)
            gave_up_tdp = self._settings.manage_tdp is True and updated.manage_tdp is not True
            self._settings = updated
            await self._follow_settings()
            if gave_up_tdp:
                owner = (await self.conflicts()).power
                await asyncio.to_thread(self._power.give_back_tdp, owner)
            return self._settings

    async def preview_lighting(self, lighting: Lighting) -> None:
        """Show lighting on the rings without keeping it, while the user picks a colour.

        Applying keeps it through update_settings; cancelling sends the saved lighting back.
        """
        await self._started()
        await self._display.send_lighting(lighting)

    async def gyro(self) -> GyroState:
        """Whether the gyroscope's axes need ORIGAMI here, and what ORIGAMI has done about them."""
        return await self._gamepad.gyro_state()

    async def trigger_state(self) -> TriggerState:
        """Whether the triggers here have motors ORIGAMI can rumble."""
        return await self._gamepad.trigger_state()

    async def test_vibration(self) -> None:
        """Rumble the handles for a second, so the strength can be felt without a game."""
        await self._gamepad.test_vibration()

    async def test_trigger_rumble(self) -> None:
        """Rumble the triggers at their level as a game's full rumble would: a second, or taps."""
        await self._started()
        await self._gamepad.test_trigger_rumble(self._settings.trigger_rumble)

    async def saturation(self) -> int | None:
        """The saturation gamescope shows now, ORIGAMI's or not; None without gamescope."""
        return await self._display.saturation()

    async def restore_saturation(self) -> None:
        """Send the saved saturation again; the frontend calls it whenever Steam's interface loads.

        gamescope forgets the property when it restarts, Steam sets its own value as it starts, and
        within a tenth of a second of every resume the property is back at sRGB (watched on the
        console), so it is also sent after each resume.
        """
        await self._started()
        async with self._settings_lock:
            await self._display.restore_saturation(self._settings)

    async def power(self) -> HeldPower:
        """The limits ORIGAMI holds now, for the Power screen."""
        return self._power.held()

    async def set_steam_tdp_limit(self, *, on: bool) -> None:
        """Steam's TDP slider was switched on or off; see PowerBlock.set_steam_tdp_limit."""
        await self._started()
        async with self._settings_lock:
            await self._power.set_steam_tdp_limit(self._settings, on=on)

    async def set_game(self, app_id: int | None) -> None:
        """Steam runs this game now, or none: the power follows the game's own profile, if any."""
        await self._started()
        async with self._settings_lock:
            await self._power.set_game(self._settings, app_id)

    async def game_started(self) -> None:
        """Steam started a game: it writes its own limits meanwhile, so ORIGAMI writes again."""
        self._power.game_started()

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
            await self._gamepad.close_rumble()
            owners = await self.conflicts()
            await asyncio.to_thread(self._power.give_back_tdp, owners.power)
            await asyncio.to_thread(self._power.give_back_boost, owners.power)
            async with self._controller_lock:
                await asyncio.to_thread(self._give_back_controller, owners)
            await self._display.give_back_saturation(owners.saturation)
            try:
                await self._gamepad.set_gyro(on=False)
            except (CommandError, OSError, RuntimeError, TimeoutError) as error:
                log.warning("Gyroscope not given back: %s", error)
            log.info("Everything given back, %d changes left", len(self._journal.entries()))
            return self._settings

    def _read_conflicts(self) -> Conflicts:
        return read_conflicts(self._env.decky_home)

    def uninstall(self) -> None:
        """Give the system back as it was, when Decky removes the plugin; the settings stay.

        Decky also removes and installs the plugin to update it. Nothing here may wait (see stop),
        so InputPlumber is not restarted: it takes the stock axes when it starts next. The firmware
        gets its platform profile's own power back, and the CPU boost what it was before ORIGAMI;
        gamescope gets its saturation back through a blocking xprop, as the magnifier is switched
        off. What another plugin drives now stays as it set it. A part that fails is logged, and
        the rest is given back all the same.
        """
        owners = self._read_conflicts()
        self._gamepad.remove_gyro_fix()
        self._fans.give_back(owners.fans)
        self._power.give_back_tdp(owners.power)
        self._power.give_back_boost(owners.power)
        self._give_back_controller(owners)
        self._display.give_back_saturation_now(owners.saturation)
        log.info("ORIGAMI uninstalled")

    def stop(self) -> None:
        """Cancel background work before Decky unloads the plugin, without waiting for it.

        Decky ends the process right after unloading, and while the unload waits, Decky 3.3.0's
        own socket listener spins on the closed socket and freezes the event loop, so a waiting
        unload never returns and Decky kills the plugin after 5 s. A vibration test still running
        is stopped right away, the rumble program leaves the controller, and the magnifier goes
        off with the right stick given back to the game.
        """
        self._after_resume.cancel()
        self._fans.stop()
        self._power.stop()
        self._gamepad.stop()
        self._buttons.stop()
        log.info("ORIGAMI stopped")

    async def _follow_settings(self) -> None:
        settings = self._settings
        await self._power.follow(settings)
        await self._fans.follow(settings)
        await self._buttons.follow(settings)
        # The controller forgets ORIGAMI's lighting and vibration in sleep, and may come back as
        # new devices without the rumble program; the saturation goes back to Steam's on resume.
        await self._after_resume.run_while(
            on=settings.lighting is not None
            or settings.vibration is not None
            or settings.trigger_rumble is not None
            or settings.saturation is not None
        )

    def _give_back_controller(self, owners: Conflicts) -> None:
        """The rings and the handles' strength as they were before ORIGAMI; blocks briefly.

        A plugin that drives them now keeps them as it set them: only ORIGAMI's record goes.
        """
        self._display.give_back_lighting(owners.lighting)
        self._gamepad.give_back_vibration(owners.vibration)

    async def _restore_controller(self) -> None:
        """Send the saved lighting, vibration and rumble program again, at start and after sleep.

        Failures are only logged: the controller may be gone, or another plugin drives it now.
        """
        await self._display.restore_lighting(self._settings)
        await self._gamepad.restore(self._settings)

    async def _follow_resumes(self) -> None:
        async with aclosing(resumes()) as wakes:
            async for _ in wakes:
                await asyncio.sleep(RESUME_SETTLE_SECONDS)
                # A change saved meanwhile is not overwritten by what was set before it.
                async with self._settings_lock:
                    await self._restore_controller()
                    await self._display.restore_saturation(self._settings)

    async def _board(self) -> str | None:
        return (await self.info()).device.board

    def _board_now(self) -> str | None:
        return self._info.device.board if self._info else None

    async def _started(self) -> None:
        await self._ready.wait()
        if self._start_error is not None:
            raise RuntimeError("ORIGAMI failed to start, see the plugin log") from self._start_error
