# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import json
import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest

from origami import app as app_module
from origami import gyro as gyro_module
from origami import power as power_module
from origami import versions
from origami.app import BUTTON_ACTION, QAM_PRESSED, Emit, Environment, Origami
from origami.buttons import ButtonAction
from origami.decky_plugins import (
    FAN_OWNERS,
    LIGHTING_OWNERS,
    POWER_OWNERS,
    SATURATION_OWNERS,
    TRIGGER_OWNERS,
    VIBRATION_OWNERS,
)
from origami.gyro import GyroState
from origami.inputplumber import Chord
from origami.journal import Change
from origami.jsonio import JsonValue
from origami.lighting import CONTROLLER_LIGHTING, Lighting, LightMode
from origami.magnifier import Magnifier
from origami.power import Power, PowerKeeper
from origami.proc import CommandError
from origami.rumble import SETTINGS_MAP
from origami.settings import Language, Settings, SettingsStore
from origami.tdp import Limits
from origami.triggers import TriggerLevel, TriggerRumble, Triggers, TriggerState
from origami.vibration import Vibration

from fakes import FakeHidBpf, FakeRoot


@pytest.fixture(autouse=True)
def no_busctl(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run(*_args: str) -> str:
        return '{"type":"s","data":"0.83.0"}'

    monkeypatch.setattr(versions, "run", fake_run)


async def no_events(_event: str, *_args: JsonValue) -> None:
    pass


def make_app(
    root: FakeRoot,
    tmp_path: Path,
    emit: Emit = no_events,
    bpf: FakeHidBpf | None = None,
    *,
    first_start: bool = False,
) -> Origami:
    settings = tmp_path / "settings" / "settings.json"
    if not first_start and not settings.exists():
        # Saved by an install before the handles' default strength: the controller keeps its
        # own, so a test sees only what it sets itself.
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text('{"vibration": null}\n', encoding="utf-8")
    environment = Environment(
        root=root.path,
        settings_dir=tmp_path / "settings",
        data_dir=tmp_path / "data",
        decky_home=tmp_path / "decky",
        plugin_dir=tmp_path / "plugin",
        version="0.1.0",
        decky_version="v3.3.0",
    )
    return Origami(environment, emit=emit, attach_bpf=bpf or FakeHidBpf())


def install_plugin(tmp_path: Path, name: str) -> None:
    manifest = tmp_path / "decky" / "plugins" / name / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"name": name}), encoding="utf-8")


@pytest.fixture
def sent_lighting(monkeypatch: pytest.MonkeyPatch) -> list[Lighting]:
    """Lighting the app sends to the controller, in order."""
    sent: list[Lighting] = []

    def apply(_root: Path, lighting: Lighting) -> None:
        sent.append(lighting)

    monkeypatch.setattr(app_module, "apply_lighting", apply)
    return sent


@pytest.fixture
def sent_vibration(monkeypatch: pytest.MonkeyPatch) -> list[Vibration]:
    """Vibration strengths the app sent to the controller."""
    sent: list[Vibration] = []

    def apply(_root: Path, vibration: Vibration) -> None:
        sent.append(vibration)

    monkeypatch.setattr(app_module, "apply_vibration", apply)
    return sent


def test_info_after_start(ally_x: FakeRoot, tmp_path: Path) -> None:
    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()
        info = await app.info()

        assert info.version == "0.1.0"
        assert info.device.model == "ROG Xbox Ally X"
        assert info.versions.inputplumber == "0.83.0"
        assert await app.changes() == []

    asyncio.run(scenario())


def test_calls_wait_for_start(ally_x: FakeRoot, tmp_path: Path) -> None:
    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        pending = asyncio.create_task(app.settings())
        await asyncio.sleep(0)
        assert not pending.done()

        await app.start()

        assert await pending == Settings(vibration=None)

    asyncio.run(scenario())


def test_failed_start_is_reported_to_callers(
    ally_x: FakeRoot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_root: Path) -> None:
        raise PermissionError("dmi")

    monkeypatch.setattr(app_module, "read_device", broken)

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()
        with pytest.raises(RuntimeError, match="failed to start"):
            await app.info()

    asyncio.run(scenario())


def test_settings_are_saved(ally_x: FakeRoot, tmp_path: Path) -> None:
    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()
        assert await app.update_settings({"language": "en"}) == Settings(
            language=Language.EN, vibration=None
        )

        restarted = make_app(ally_x, tmp_path)
        await restarted.start()
        assert await restarted.settings() == Settings(language=Language.EN, vibration=None)

    asyncio.run(scenario())


def test_telemetry(ally_x: FakeRoot, tmp_path: Path) -> None:
    telemetry = asyncio.run(make_app(ally_x, tmp_path).telemetry())

    assert telemetry.power.tdp_limit_w == 17


def test_qam_assist_forwards_presses_while_it_is_on(ally_x: FakeRoot, tmp_path: Path) -> None:
    press = bytes.fromhex("5a9300000000")
    node = ally_x.hidraw(5, driver="asus_rog_ally", phys="usb-0000:66:00.0-4/input2")

    async def scenario() -> None:
        events: list[str] = []
        received = asyncio.Event()

        async def emit(event: str, *_args: JsonValue) -> None:
            events.append(event)
            received.set()

        writer = os.open(node, os.O_RDWR | os.O_NONBLOCK)
        app = make_app(ally_x, tmp_path, emit)
        await app.start()
        assert (await app.settings()).qam_assist is None

        await app.update_settings({"qam_assist": True})
        await asyncio.sleep(0.05)
        os.write(writer, press)
        async with asyncio.timeout(1):
            await received.wait()
        assert events == [QAM_PRESSED]

        await app.update_settings({"qam_assist": False})
        os.write(writer, press)
        await asyncio.sleep(0.05)
        assert events == [QAM_PRESSED]

        app.stop()
        os.close(writer)

    asyncio.run(scenario())


def test_qam_assist_starts_with_the_plugin_when_it_was_on(ally_x: FakeRoot, tmp_path: Path) -> None:
    press = bytes.fromhex("5a9300000000")
    node = ally_x.hidraw(5, driver="asus_rog_ally", phys="usb-0000:66:00.0-4/input2")

    async def scenario() -> None:
        events: list[str] = []
        received = asyncio.Event()

        async def emit(event: str, *_args: JsonValue) -> None:
            events.append(event)
            received.set()

        first = make_app(ally_x, tmp_path)
        await first.start()
        await first.update_settings({"qam_assist": True})
        first.stop()

        writer = os.open(node, os.O_RDWR | os.O_NONBLOCK)
        app = make_app(ally_x, tmp_path, emit)
        await app.start()
        await asyncio.sleep(0.05)
        os.write(writer, press)
        async with asyncio.timeout(1):
            await received.wait()
        assert events == [QAM_PRESSED]
        app.stop()
        os.close(writer)

    asyncio.run(scenario())


RAINBOW = {"mode": "rainbow", "left": 0xFF0000, "right": 0xFF0000, "speed": "fast"}


def test_lighting_is_sent_kept_and_journaled(
    ally_x: FakeRoot, tmp_path: Path, sent_lighting: list[Lighting]
) -> None:
    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()
        assert sent_lighting == []

        settings = await app.update_settings({"lighting": RAINBOW})

        assert sent_lighting == [Lighting.from_json(RAINBOW)]
        assert settings.lighting is not None and settings.lighting.mode is LightMode.RAINBOW
        assert await app.changes() == [Change("lighting", "rings", None)]
        app.stop()

    asyncio.run(scenario())


def test_lighting_is_left_alone_while_a_lighting_plugin_runs(
    ally_x: FakeRoot, tmp_path: Path, sent_lighting: list[Lighting]
) -> None:
    install_plugin(tmp_path, LIGHTING_OWNERS[0])

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()
        assert (await app.conflicts()).lighting == LIGHTING_OWNERS[0]

        with pytest.raises(RuntimeError, match=LIGHTING_OWNERS[0]):
            await app.update_settings({"lighting": RAINBOW})

        assert sent_lighting == []
        assert (await app.settings()).lighting is None
        assert await app.changes() == []

    asyncio.run(scenario())


def test_saved_lighting_comes_back_at_start_and_after_sleep(
    ally_x: FakeRoot, tmp_path: Path, sent_lighting: list[Lighting], monkeypatch: pytest.MonkeyPatch
) -> None:
    woke = asyncio.Event()

    async def one_resume() -> AsyncGenerator[None]:
        yield
        woke.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(app_module, "resumes", one_resume)
    monkeypatch.setattr(app_module, "RESUME_SETTLE_SECONDS", 0)

    async def scenario() -> None:
        first = make_app(ally_x, tmp_path)
        await first.start()
        await first.update_settings({"lighting": RAINBOW})
        first.stop()
        sent_lighting.clear()

        app = make_app(ally_x, tmp_path)
        await app.start()
        async with asyncio.timeout(1):
            await woke.wait()

        assert sent_lighting == [Lighting.from_json(RAINBOW)] * 2
        app.stop()

    asyncio.run(scenario())


def test_previewed_lighting_is_shown_but_not_kept(
    ally_x: FakeRoot, tmp_path: Path, sent_lighting: list[Lighting]
) -> None:
    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()
        preview = Lighting(mode=LightMode.STATIC, left=0x8CFFE2, right=0x8CFFE2)

        await app.preview_lighting(preview)

        assert sent_lighting == [preview]
        assert (await app.settings()).lighting is None

    asyncio.run(scenario())


def test_stop_cancels_background_work_without_waiting(ally_x: FakeRoot, tmp_path: Path) -> None:
    press = bytes.fromhex("5a9300000000")
    node = ally_x.hidraw(5, driver="asus_rog_ally", phys="usb-0000:66:00.0-4/input2")

    async def scenario() -> None:
        events: list[str] = []

        async def emit(event: str, *_args: JsonValue) -> None:
            events.append(event)

        writer = os.open(node, os.O_RDWR | os.O_NONBLOCK)
        app = make_app(ally_x, tmp_path, emit)
        await app.start()
        await app.update_settings({"qam_assist": True})
        await asyncio.sleep(0.05)

        # Decky unloads synchronously: the call returns at once, the work stops on the next turn.
        assert app.stop() is None
        await asyncio.sleep(0)
        os.write(writer, press)
        await asyncio.sleep(0.05)

        assert events == []
        os.close(writer)

    asyncio.run(scenario())


def test_a_saturation_plugin_owns_the_saturation(ally_x: FakeRoot, tmp_path: Path) -> None:
    install_plugin(tmp_path, SATURATION_OWNERS[0])

    conflicts = asyncio.run(make_app(ally_x, tmp_path).conflicts())

    assert (conflicts.lighting, conflicts.saturation) == (None, SATURATION_OWNERS[0])


@pytest.mark.parametrize("plugin", VIBRATION_OWNERS)
def test_vibration_plugins_own_the_vibration(ally_x: FakeRoot, tmp_path: Path, plugin: str) -> None:
    install_plugin(tmp_path, plugin)

    assert asyncio.run(make_app(ally_x, tmp_path).conflicts()).vibration == plugin


@pytest.fixture
def screen(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[int] | int]:
    """gamescope's saturation as the app reads and writes it."""
    state: dict[str, list[int] | int] = {"now": 100, "written": []}

    async def read(_root: Path) -> int:
        now = state["now"]
        assert isinstance(now, int)
        return now

    async def write(_root: Path, percent: int) -> None:
        written = state["written"]
        assert isinstance(written, list)
        written.append(percent)
        state["now"] = percent

    monkeypatch.setattr(app_module, "read_saturation", read)
    monkeypatch.setattr(app_module, "write_saturation", write)
    return state


def test_saturation_is_written_kept_journaled_and_restored(
    ally_x: FakeRoot, tmp_path: Path, screen: dict[str, list[int] | int]
) -> None:
    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()
        await app.restore_saturation()
        assert screen["written"] == []

        settings = await app.update_settings({"saturation": 150})

        assert settings.saturation == 150
        assert screen["written"] == [150]
        assert await app.changes() == [Change("display", "saturation", 100)]

        # gamescope restarts and Steam sets its own value; the frontend asks for ORIGAMI's again.
        screen["now"] = 100
        await app.restore_saturation()
        assert screen["written"] == [150, 150]

    asyncio.run(scenario())


def test_saturation_is_not_set_while_gamescope_cannot_be_read(
    ally_x: FakeRoot,
    tmp_path: Path,
    screen: dict[str, list[int] | int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unreachable(_root: Path) -> int:
        raise CommandError("gamescope's display is not there")

    monkeypatch.setattr(app_module, "read_saturation", unreachable)

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()

        with pytest.raises(CommandError):
            await app.update_settings({"saturation": 150})

        assert screen["written"] == []
        assert await app.changes() == []
        assert await app.saturation() is None
        app.stop()

    asyncio.run(scenario())


def test_a_saturation_nobody_had_set_is_given_back_as_srgb(
    ally_x: FakeRoot,
    tmp_path: Path,
    screen: dict[str, list[int] | int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unset(_root: Path) -> None:
        return None

    monkeypatch.setattr(app_module, "read_saturation", unset)

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()
        assert await app.saturation() == 100

        await app.update_settings({"saturation": 150})
        assert await app.changes() == [Change("display", "saturation", None)]

        await app.restore_all()

        assert screen["written"] == [150, 100]
        app.stop()

    asyncio.run(scenario())


def test_saturation_comes_back_after_sleep(
    ally_x: FakeRoot,
    tmp_path: Path,
    screen: dict[str, list[int] | int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    woke = asyncio.Event()

    async def one_resume() -> AsyncGenerator[None]:
        yield
        woke.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(app_module, "resumes", one_resume)
    monkeypatch.setattr(app_module, "RESUME_SETTLE_SECONDS", 0)

    async def scenario() -> None:
        first = make_app(ally_x, tmp_path)
        await first.start()
        await first.update_settings({"saturation": 150})
        first.stop()
        screen["now"] = 100  # the property is back at sRGB right after a resume

        app = make_app(ally_x, tmp_path)
        await app.start()
        async with asyncio.timeout(1):
            await woke.wait()

        assert screen["written"] == [150, 150]
        app.stop()

    asyncio.run(scenario())


def test_saturation_is_left_alone_while_a_saturation_plugin_runs(
    ally_x: FakeRoot, tmp_path: Path, screen: dict[str, list[int] | int]
) -> None:
    install_plugin(tmp_path, SATURATION_OWNERS[0])

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()

        with pytest.raises(RuntimeError, match=SATURATION_OWNERS[0]):
            await app.update_settings({"saturation": 150})

        assert screen["written"] == []
        assert (await app.settings()).saturation is None

    asyncio.run(scenario())


def test_vibration_is_sent_kept_and_journaled_with_the_driver_strength(
    ally_x: FakeRoot, tmp_path: Path, sent_vibration: list[Vibration]
) -> None:
    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()
        assert sent_vibration == []

        settings = await app.update_settings({"vibration": {"left": 25, "right": 75}})
        await app.update_settings({"vibration": {"left": 30, "right": 30}})

        assert sent_vibration == [Vibration(left=25, right=75), Vibration(left=30, right=30)]
        assert settings.vibration == Vibration(left=25, right=75)
        assert await app.changes() == [Change("gamepad", "vibration", [50, 50])]
        app.stop()

    asyncio.run(scenario())


def test_the_first_start_sets_the_handles_to_the_middle_level(
    ally_x: FakeRoot, tmp_path: Path, sent_vibration: list[Vibration]
) -> None:
    async def scenario() -> None:
        app = make_app(ally_x, tmp_path, first_start=True)
        await app.start()

        assert sent_vibration == [Vibration(left=50, right=50)]
        assert (await app.settings()).vibration == Vibration(left=50, right=50)
        assert await app.changes() == [Change("gamepad", "vibration", [50, 50])]
        app.stop()

    asyncio.run(scenario())


def test_the_first_start_leaves_the_vibration_to_a_vibration_plugin(
    ally_x: FakeRoot, tmp_path: Path, sent_vibration: list[Vibration]
) -> None:
    install_plugin(tmp_path, VIBRATION_OWNERS[0])

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path, first_start=True)
        await app.start()

        assert sent_vibration == []
        assert await app.changes() == []
        app.stop()

    asyncio.run(scenario())


def test_vibration_is_left_alone_while_a_vibration_plugin_runs(
    ally_x: FakeRoot, tmp_path: Path, sent_vibration: list[Vibration]
) -> None:
    install_plugin(tmp_path, VIBRATION_OWNERS[0])

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()

        with pytest.raises(RuntimeError, match=VIBRATION_OWNERS[0]):
            await app.update_settings({"vibration": {"left": 30, "right": 30}})

        assert sent_vibration == []
        assert (await app.settings()).vibration is None
        assert await app.changes() == []

    asyncio.run(scenario())


def test_saved_vibration_comes_back_at_start_and_after_sleep(
    ally_x: FakeRoot,
    tmp_path: Path,
    sent_vibration: list[Vibration],
    sent_lighting: list[Lighting],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    woke = asyncio.Event()

    async def one_resume() -> AsyncGenerator[None]:
        yield
        woke.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(app_module, "resumes", one_resume)
    monkeypatch.setattr(app_module, "RESUME_SETTLE_SECONDS", 0)

    async def scenario() -> None:
        first = make_app(ally_x, tmp_path)
        await first.start()
        await first.update_settings({"vibration": {"left": 20, "right": 20}})
        first.stop()
        sent_vibration.clear()

        app = make_app(ally_x, tmp_path)
        await app.start()
        async with asyncio.timeout(1):
            await woke.wait()

        assert sent_vibration == [Vibration(left=20, right=20)] * 2
        assert sent_lighting == []
        app.stop()

    asyncio.run(scenario())


@pytest.fixture
def rumbles(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """What the app told the motors, with a pulse of a few milliseconds."""
    told: list[str] = []

    def pulse(_root: Path) -> None:
        told.append("pulse")

    def stop(_root: Path) -> None:
        told.append("stop")

    monkeypatch.setattr(app_module, "start_pulse", pulse)
    monkeypatch.setattr(app_module, "stop_rumble", stop)
    monkeypatch.setattr(app_module, "PULSE_SECONDS", 0.02)
    return told


def test_trigger_rumble_attaches_the_program_and_keeps_the_setting(
    ally_x: FakeRoot, tmp_path: Path
) -> None:
    ally_x.ally_controller()
    bpf = FakeHidBpf()

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path, bpf=bpf)
        await app.start()
        assert await app.trigger_state() is TriggerState.AVAILABLE
        assert bpf.programs == []

        settings = await app.update_settings(
            {"trigger_rumble": {"enabled": True, "triggers": "right"}}
        )

        assert settings.trigger_rumble == TriggerRumble(True, Triggers.RIGHT, TriggerLevel.MEDIUM)
        [program] = bpf.attached()
        assert program.path == tmp_path / "plugin/bin/rumble.bpf.o"
        assert program.maps[SETTINGS_MAP] == [bytes([0, 60, 0, 0])]

        await app.update_settings({"trigger_rumble": {"enabled": True, "taps": True}})
        assert program.maps[SETTINGS_MAP][-1] == bytes([0, 60, 0, 1])
        # Nothing stays in the system: the program goes with the plugin.
        assert await app.changes() == []

        app.stop()
        assert bpf.attached() == []

    asyncio.run(scenario())


def test_saved_trigger_rumble_comes_back_at_start(ally_x: FakeRoot, tmp_path: Path) -> None:
    ally_x.ally_controller()
    bpf = FakeHidBpf()

    async def scenario() -> None:
        first = make_app(ally_x, tmp_path, bpf=bpf)
        await first.start()
        await first.update_settings(
            {"trigger_rumble": {"enabled": True, "triggers": "both", "level": "max"}}
        )
        first.stop()

        app = make_app(ally_x, tmp_path, bpf=bpf)
        await app.start()

        [program] = bpf.attached()
        assert program.maps[SETTINGS_MAP] == [bytes([100, 100, 0, 0])]
        app.stop()

    asyncio.run(scenario())


def test_a_trigger_plugin_owns_the_triggers(ally_x: FakeRoot, tmp_path: Path) -> None:
    ally_x.ally_controller()
    install_plugin(tmp_path, TRIGGER_OWNERS[0])
    bpf = FakeHidBpf()

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path, bpf=bpf)
        await app.start()
        assert (await app.conflicts()).triggers == TRIGGER_OWNERS[0]

        with pytest.raises(RuntimeError, match=TRIGGER_OWNERS[0]):
            await app.update_settings({"trigger_rumble": {"enabled": True, "triggers": "right"}})

        assert bpf.programs == []
        assert (await app.settings()).trigger_rumble is None

    asyncio.run(scenario())


def test_grips_are_lifted_under_origamis_own_strength(
    ally_x: FakeRoot, tmp_path: Path, sent_vibration: list[Vibration]
) -> None:
    ally_x.ally_controller()
    bpf = FakeHidBpf()

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path, bpf=bpf)
        await app.start()
        assert bpf.programs == []  # before the user sets a strength, games rumble as before

        await app.update_settings({"vibration": {"left": 80, "right": 80}})
        await app.update_settings({"trigger_rumble": {"enabled": True, "triggers": "right"}})

        assert sent_vibration == [Vibration(left=80, right=80)]
        [program] = bpf.attached()
        assert program.maps[SETTINGS_MAP] == [bytes([0, 0, 70, 0]), bytes([0, 60, 70, 0])]
        app.stop()

    asyncio.run(scenario())


def test_switched_off_handles_get_zero_and_no_lift(
    ally_x: FakeRoot, tmp_path: Path, sent_vibration: list[Vibration]
) -> None:
    ally_x.ally_controller()
    bpf = FakeHidBpf()

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path, bpf=bpf)
        await app.start()
        await app.update_settings({"vibration": {"left": 80, "right": 80}})

        settings = await app.update_settings(
            {"vibration": {"enabled": False, "left": 80, "right": 80}}
        )

        assert settings.vibration == Vibration(enabled=False, left=80, right=80)
        assert bpf.attached() == []
        app.stop()

    asyncio.run(scenario())
    assert sent_vibration == [
        Vibration(left=80, right=80),
        Vibration(enabled=False, left=80, right=80),
    ]


def test_grips_are_left_alone_while_another_plugin_sets_the_strength(
    ally_x: FakeRoot, tmp_path: Path, sent_vibration: list[Vibration]
) -> None:
    ally_x.ally_controller()
    bpf = FakeHidBpf()

    async def scenario() -> None:
        first = make_app(ally_x, tmp_path, bpf=bpf)
        await first.start()
        await first.update_settings({"vibration": {"left": 80, "right": 80}})
        first.stop()
        install_plugin(tmp_path, VIBRATION_OWNERS[0])

        app = make_app(ally_x, tmp_path, bpf=bpf)
        await app.start()

        assert bpf.attached() == []
        app.stop()

    asyncio.run(scenario())
    assert sent_vibration == [Vibration(left=80, right=80)]


def test_the_strength_is_kept_when_the_grips_cannot_be_lifted(
    ally_x: FakeRoot, tmp_path: Path, sent_vibration: list[Vibration]
) -> None:
    # Without the controller's gamepad interface the program has nowhere to go.
    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()

        settings = await app.update_settings({"vibration": {"left": 80, "right": 80}})

        assert settings.vibration == Vibration(left=80, right=80)

    asyncio.run(scenario())
    assert sent_vibration == [Vibration(left=80, right=80)]


def test_vibration_test_is_a_pulse_that_ends_with_a_stop(
    ally_x: FakeRoot, tmp_path: Path, rumbles: list[str]
) -> None:
    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        first = asyncio.create_task(app.test_vibration())
        await asyncio.sleep(0)
        await app.test_vibration()  # pressed again during the pulse
        await first

    asyncio.run(scenario())

    assert rumbles == ["pulse", "stop"]


def test_the_handle_test_keeps_the_triggers_still(
    ally_x: FakeRoot, tmp_path: Path, rumbles: list[str]
) -> None:
    ally_x.ally_controller()
    bpf = FakeHidBpf()

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path, bpf=bpf)
        await app.start()
        await app.update_settings({"trigger_rumble": {"enabled": True, "triggers": "right"}})

        await app.test_vibration()

        assert bpf.attached()[0].maps[SETTINGS_MAP] == [
            bytes([0, 60, 0, 0]),
            bytes(4),
            bytes([0, 60, 0, 0]),
        ]
        app.stop()

    asyncio.run(scenario())
    assert rumbles == ["pulse", "stop"]


def test_trigger_test_is_a_pulse_of_the_chosen_triggers(
    ally_x: FakeRoot, tmp_path: Path, rumbles: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    ally_x.ally_controller()
    pulses: list[TriggerRumble] = []

    def pulse(_root: Path, trigger_rumble: TriggerRumble) -> None:
        pulses.append(trigger_rumble)

    monkeypatch.setattr(app_module, "start_trigger_pulse", pulse)

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()
        await app.test_trigger_rumble()  # the triggers are off: nothing to feel
        await app.update_settings(
            {"trigger_rumble": {"enabled": True, "triggers": "both", "level": "soft"}}
        )

        await app.test_trigger_rumble()

        app.stop()

    asyncio.run(scenario())
    assert pulses == [TriggerRumble(True, Triggers.BOTH, TriggerLevel.SOFT)]
    assert rumbles == ["stop"]


def test_trigger_test_taps_when_the_triggers_tap(
    ally_x: FakeRoot, tmp_path: Path, rumbles: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    ally_x.ally_controller()
    pulses: list[TriggerRumble] = []

    def pulse(_root: Path, trigger_rumble: TriggerRumble) -> None:
        pulses.append(trigger_rumble)
        rumbles.append("tap")

    monkeypatch.setattr(app_module, "start_trigger_pulse", pulse)
    monkeypatch.setattr(app_module, "TAP_SECONDS", 0.01)
    monkeypatch.setattr(app_module, "TAP_GAP_SECONDS", 0.01)

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()
        await app.update_settings({"trigger_rumble": {"enabled": True, "taps": True}})

        await app.test_trigger_rumble()

        app.stop()

    asyncio.run(scenario())
    assert len(pulses) == 3
    assert rumbles == ["tap", "stop"] * 3


def test_a_cancelled_or_unloaded_vibration_test_still_stops_the_motors(
    ally_x: FakeRoot, tmp_path: Path, rumbles: list[str]
) -> None:
    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        cancelled = asyncio.create_task(app.test_vibration())
        await asyncio.sleep(0.005)
        cancelled.cancel()
        await asyncio.gather(cancelled, return_exceptions=True)
        assert rumbles == ["pulse", "stop"]

        unloaded = asyncio.create_task(app.test_vibration())
        await asyncio.sleep(0.005)
        app.stop()
        # Decky unloads synchronously: the stop is out before anything else runs.
        assert rumbles == ["pulse", "stop", "pulse", "stop"]
        await unloaded
        assert rumbles == ["pulse", "stop", "pulse", "stop"]

    asyncio.run(scenario())


def test_armoury_crate_presses_bring_their_actions(ally_x: FakeRoot, tmp_path: Path) -> None:
    short_press = bytes.fromhex("5aa600000000")
    hold = bytes.fromhex("0100007000000000")

    async def scenario() -> None:
        config = ally_x.ally_controller()
        events: asyncio.Queue[tuple[str, ...]] = asyncio.Queue()

        async def emit(event: str, *args: JsonValue) -> None:
            events.put_nowait((event, *(str(arg) for arg in args)))

        config_writer = os.open(config, os.O_RDWR | os.O_NONBLOCK)
        keyboard_writer = os.open(ally_x.path / "dev" / "hidraw2", os.O_RDWR | os.O_NONBLOCK)
        app = make_app(ally_x, tmp_path, emit)
        await app.start()
        settings = await app.update_settings({"armoury_crate": "origami"})
        assert settings.armoury_crate is ButtonAction.ORIGAMI
        await asyncio.sleep(0.05)

        os.write(config_writer, short_press)
        assert await asyncio.wait_for(events.get(), 1) == (BUTTON_ACTION, "origami")

        # Holding the button comes from the keyboard interface: the reader starts again with it.
        await app.update_settings({"armoury_crate_hold": "performance"})
        await asyncio.sleep(0.05)
        os.write(keyboard_writer, hold)
        assert await asyncio.wait_for(events.get(), 1) == (BUTTON_ACTION, "performance")

        # Another action for a button already read takes effect with the next press.
        await app.update_settings({"armoury_crate": "quick_access"})
        os.write(config_writer, short_press)
        assert await asyncio.wait_for(events.get(), 1) == (BUTTON_ACTION, "quick_access")

        app.stop()
        os.close(config_writer)
        os.close(keyboard_writer)

    asyncio.run(scenario())


def test_buttons_are_not_read_until_something_is_assigned(ally_x: FakeRoot, tmp_path: Path) -> None:
    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()
        settings = await app.settings()

        assert (settings.armoury_crate, settings.armoury_crate_hold) == (None, None)
        assert not any(task.get_name() == "origami-buttons" for task in asyncio.all_tasks())

        await app.update_settings({"armoury_crate": "none"})
        assert not any(task.get_name() == "origami-buttons" for task in asyncio.all_tasks())

    asyncio.run(scenario())


def test_steam_buttons_are_pressed_and_other_actions_go_to_the_frontend(
    ally_x: FakeRoot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    short_press = bytes.fromhex("5aa600000000")
    pressed: list[Chord] = []

    def press(_root: Path, chord: Chord) -> None:
        pressed.append(chord)

    monkeypatch.setattr(app_module, "press_chord", press)

    async def scenario() -> None:
        config = ally_x.ally_controller()
        events: asyncio.Queue[tuple[str, ...]] = asyncio.Queue()

        async def emit(event: str, *args: JsonValue) -> None:
            events.put_nowait((event, *(str(arg) for arg in args)))

        writer = os.open(config, os.O_RDWR | os.O_NONBLOCK)
        app = make_app(ally_x, tmp_path, emit)
        await app.start()
        await app.update_settings({"armoury_crate": "screenshot"})
        await asyncio.sleep(0.05)

        os.write(writer, short_press)
        await asyncio.sleep(0.05)
        await app.update_settings({"armoury_crate": "l5"})
        os.write(writer, short_press)
        await asyncio.sleep(0.05)
        assert pressed == [Chord.SCREENSHOT, Chord.L5]
        assert events.empty()

        await app.update_settings({"armoury_crate": "overlay"})
        os.write(writer, short_press)
        assert await asyncio.wait_for(events.get(), 1) == (BUTTON_ACTION, "overlay")
        assert pressed == [Chord.SCREENSHOT, Chord.L5]

        app.stop()
        os.close(writer)

    asyncio.run(scenario())


def test_the_button_switches_the_magnifier(
    ally_x: FakeRoot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    switched: list[Magnifier] = []

    def toggle(magnifier: Magnifier) -> bool:
        switched.append(magnifier)
        return True

    monkeypatch.setattr(Magnifier, "toggle", toggle)

    async def scenario() -> None:
        config = ally_x.ally_controller()
        writer = os.open(config, os.O_RDWR | os.O_NONBLOCK)
        app = make_app(ally_x, tmp_path)
        await app.start()
        await app.update_settings({"armoury_crate": "magnifier"})
        await asyncio.sleep(0.05)

        os.write(writer, bytes.fromhex("5aa600000000"))
        await asyncio.sleep(0.05)

        assert len(switched) == 1
        app.stop()
        os.close(writer)

    asyncio.run(scenario())


@pytest.fixture
def inputplumber(ally_x: FakeRoot, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """InputPlumber's stock device file on the console; restarts of InputPlumber are counted."""
    stock = ally_x.path / gyro_module.STOCK
    stock.parent.mkdir(parents=True)
    stock.write_text("source_devices:\n  - group: imu\n          z: [0, 1, 0]\n", encoding="utf-8")
    (ally_x.path / gyro_module.OVERRIDE).parent.mkdir(parents=True)
    restarts: list[str] = []

    async def restart() -> None:
        restarts.append("inputplumber")

    monkeypatch.setattr(app_module, "restart_inputplumber", restart)
    return restarts


def test_the_gyroscope_fix_is_written_and_taken_back(
    ally_x: FakeRoot, tmp_path: Path, inputplumber: list[str]
) -> None:
    override = ally_x.path / gyro_module.OVERRIDE

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()
        assert await app.gyro() is GyroState.WRONG
        assert inputplumber == []

        settings = await app.update_settings({"gyro_fix": True})

        assert settings.gyro_fix is True
        assert override.exists()
        assert await app.gyro() is GyroState.FIXED
        assert await app.changes() == [Change("gamepad", "gyro", None)]
        assert inputplumber == ["inputplumber"]

        await app.update_settings({"gyro_fix": False})

        assert not override.exists()
        assert await app.changes() == []
        assert inputplumber == ["inputplumber"] * 2

    asyncio.run(scenario())


def test_switching_off_a_gyroscope_fix_never_set_leaves_inputplumber_alone(
    ally_x: FakeRoot, tmp_path: Path, inputplumber: list[str]
) -> None:
    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()

        settings = await app.update_settings({"gyro_fix": False})

        assert settings.gyro_fix is False
        assert not (ally_x.path / gyro_module.OVERRIDE).exists()
        assert inputplumber == []

    asyncio.run(scenario())


def test_the_gyroscope_fix_follows_inputplumber_updates_at_start(
    ally_x: FakeRoot, tmp_path: Path, inputplumber: list[str]
) -> None:
    async def scenario() -> None:
        first = make_app(ally_x, tmp_path)
        await first.start()
        await first.update_settings({"gyro_fix": True})
        first.stop()
        stock = ally_x.path / gyro_module.STOCK
        stock.write_text(stock.read_text(encoding="utf-8") + "# 0.84\n", encoding="utf-8")

        app = make_app(ally_x, tmp_path)
        await app.start()

        assert await app.gyro() is GyroState.FIXED
        assert inputplumber == ["inputplumber"] * 2
        app.stop()

    asyncio.run(scenario())


def test_uninstalling_removes_the_gyroscope_fix_without_waiting(
    ally_x: FakeRoot, tmp_path: Path, inputplumber: list[str]
) -> None:
    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()
        await app.update_settings({"gyro_fix": True})
        app.stop()

        assert app.uninstall() is None

        assert not (ally_x.path / gyro_module.OVERRIDE).exists()
        assert await app.changes() == []
        # InputPlumber takes the stock axes when it starts next; the settings stay for an update.
        assert inputplumber == ["inputplumber"]
        assert (await app.settings()).gyro_fix is True

    asyncio.run(scenario())


def test_another_programs_gyroscope_file_is_left_alone(
    ally_x: FakeRoot, tmp_path: Path, inputplumber: list[str]
) -> None:
    (ally_x.path / gyro_module.OVERRIDE).write_text("# another program's axes\n", encoding="utf-8")

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()
        assert await app.gyro() is GyroState.FOREIGN

        with pytest.raises(RuntimeError, match="gyroscope"):
            await app.update_settings({"gyro_fix": True})

        assert (await app.settings()).gyro_fix is None
        assert inputplumber == []

    asyncio.run(scenario())


ARMOURY = "sys/class/firmware-attributes/asus-armoury/attributes"


async def no_supply_changes() -> AsyncGenerator[None]:
    await asyncio.Event().wait()
    yield


@pytest.fixture(autouse=True)
def quiet_supplies(monkeypatch: pytest.MonkeyPatch) -> None:
    """No kernel events about the charger; tests that need one send their own."""
    monkeypatch.setattr(app_module, "supply_changes", no_supply_changes)


@pytest.fixture
def quick_power(monkeypatch: pytest.MonkeyPatch) -> None:
    """The power keeper looks every few milliseconds instead of every two seconds."""
    monkeypatch.setattr(power_module, "POLL_SECONDS", 0.005)


def written_limits(root: FakeRoot) -> list[int]:
    return [
        int((root.path / ARMOURY / name / "current_value").read_text(encoding="utf-8"))
        for name in ("ppt_pl1_spl", "ppt_pl2_sppt", "ppt_pl3_fppt")
    ]


@pytest.mark.usefixtures("quick_power")
def test_origami_holds_the_tdp_from_the_start_and_journals_it(
    powered: FakeRoot, tmp_path: Path
) -> None:
    async def scenario() -> None:
        app = make_app(powered, tmp_path)
        await app.start()

        await app.update_settings({"power": {"tdp": 20, "headroom": True, "cpu_boost": None}})
        await asyncio.sleep(0.05)

        assert written_limits(powered) == [20, 24, 29]
        assert (await app.power()).limits == Limits(20, 24, 29)
        assert await app.changes() == [Change("power", "tdp", None)]
        app.stop()

    asyncio.run(scenario())


@pytest.mark.usefixtures("quick_power")
def test_letting_go_of_the_tdp_gives_the_firmware_its_profile_back(
    powered: FakeRoot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    given_back: list[Path] = []

    def reset(root: Path) -> bool:
        given_back.append(root)
        return True

    monkeypatch.setattr(app_module, "reset_to_profile", reset)

    async def scenario() -> None:
        app = make_app(powered, tmp_path)
        await app.start()
        await app.update_settings({"power": {"tdp": 20}})
        await asyncio.sleep(0.05)

        await app.update_settings({"manage_tdp": False})
        powered.write(f"{ARMOURY}/ppt_pl1_spl/current_value", 35)
        await asyncio.sleep(0.05)

        # The profile was written again, and ORIGAMI no longer answers other writes.
        assert given_back == [powered.path]
        assert written_limits(powered)[0] == 35
        assert (await app.power()).limits is None
        assert await app.changes() == []
        app.stop()

    asyncio.run(scenario())


@pytest.mark.usefixtures("quick_power")
def test_the_chosen_boost_is_journaled_and_given_back_on_uninstall(
    powered: FakeRoot, tmp_path: Path
) -> None:
    boost = powered.path / "sys/devices/system/cpu/cpufreq/boost"

    async def scenario() -> None:
        app = make_app(powered, tmp_path)
        await app.start()
        await app.update_settings({"power": {"cpu_boost": True}})
        await asyncio.sleep(0.05)
        assert boost.read_text(encoding="utf-8") == "1\n"
        assert Change("power", "cpu_boost", False) in await app.changes()
        app.stop()

        assert app.uninstall() is None

        assert boost.read_text(encoding="utf-8") == "0\n"
        assert await app.changes() == []

    asyncio.run(scenario())


@pytest.fixture
def fan_curves(powered: FakeRoot, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The firmware's curve device on its own curve; the fan keeper looks every few milliseconds."""
    monkeypatch.setattr(app_module, "FAN_POLL_SECONDS", 0.005)
    return powered.hwmon(8, "asus_custom_fan_curve", pwm1_enable=2, pwm2_enable=2)


def fan_mode(device: Path) -> list[int]:
    return [int((device / f"pwm{fan}_enable").read_text(encoding="utf-8")) for fan in (1, 2)]


def fan_speeds(device: Path, fan: int = 1) -> list[int]:
    return [
        int((device / f"pwm{fan}_auto_point{index}_pwm").read_text(encoding="utf-8"))
        for index in range(1, 9)
    ]


@pytest.mark.usefixtures("quick_power")
def test_origami_holds_its_fan_curve_and_gives_the_fans_back(
    powered: FakeRoot, fan_curves: Path, tmp_path: Path
) -> None:
    async def scenario() -> None:
        app = make_app(powered, tmp_path)
        await app.start()
        assert fan_mode(fan_curves) == [2, 2]

        await app.update_settings(
            {"fans": {"enabled": True, "points": [20, 30, 45, 60, 75, 90, 100]}}
        )
        assert fan_mode(fan_curves) == [1, 1]
        assert fan_speeds(fan_curves, 2) == [51, 77, 115, 153, 191, 230, 255, 255]
        assert await app.changes() == [Change("power", "tdp", None), Change("fans", "curve", None)]

        # A platform profile written by Steam switches the curve off; ORIGAMI switches it on again.
        powered.write(f"sys/class/hwmon/{fan_curves.name}/pwm1_enable", 2)
        await asyncio.sleep(0.05)
        assert fan_mode(fan_curves) == [1, 1]

        await app.update_settings(
            {"fans": {"enabled": False, "points": [20, 30, 45, 60, 75, 90, 100]}}
        )
        assert fan_mode(fan_curves) == [2, 2]
        assert Change("fans", "curve", None) not in await app.changes()
        await asyncio.sleep(0.05)
        assert fan_mode(fan_curves) == [2, 2]
        app.stop()

    asyncio.run(scenario())


@pytest.mark.usefixtures("quick_power")
def test_uninstalling_goes_on_when_the_gyroscope_file_cannot_go(
    powered: FakeRoot, fan_curves: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(_root: Path) -> bool:
        raise PermissionError("read-only")

    monkeypatch.setattr(app_module, "remove_fix", refuse)

    async def scenario() -> None:
        app = make_app(powered, tmp_path)
        await app.start()
        await app.update_settings({"fans": {"enabled": True}})
        app.stop()

        app.uninstall()

        assert fan_mode(fan_curves) == [2, 2]

    asyncio.run(scenario())


@pytest.mark.usefixtures("quick_power")
def test_uninstalling_gives_the_fans_back(
    powered: FakeRoot, fan_curves: Path, tmp_path: Path
) -> None:
    async def scenario() -> None:
        app = make_app(powered, tmp_path)
        await app.start()
        await app.update_settings({"fans": {"enabled": True}})
        app.stop()

        app.uninstall()

        assert fan_mode(fan_curves) == [2, 2]
        assert Change("fans", "curve", None) not in await app.changes()

    asyncio.run(scenario())


@pytest.mark.parametrize("plugin", FAN_OWNERS)
@pytest.mark.usefixtures("quick_power")
def test_fan_plugins_own_the_fans(
    powered: FakeRoot, fan_curves: Path, tmp_path: Path, plugin: str
) -> None:
    install_plugin(tmp_path, plugin)

    async def scenario() -> None:
        app = make_app(powered, tmp_path)
        await app.start()
        assert (await app.conflicts()).fans == plugin

        with pytest.raises(RuntimeError, match=plugin):
            await app.update_settings({"fans": {"enabled": True}})

        assert fan_mode(fan_curves) == [2, 2]
        assert (await app.settings()).fans is None
        app.stop()

    asyncio.run(scenario())


@pytest.mark.parametrize("plugin", POWER_OWNERS)
@pytest.mark.usefixtures("quick_power")
def test_power_plugins_own_the_power(powered: FakeRoot, tmp_path: Path, plugin: str) -> None:
    install_plugin(tmp_path, plugin)
    powered.write(f"{ARMOURY}/ppt_pl1_spl/current_value", 20)

    async def scenario() -> None:
        app = make_app(powered, tmp_path)
        await app.start()
        await asyncio.sleep(0.05)
        assert (await app.conflicts()).power == plugin

        with pytest.raises(RuntimeError, match=plugin):
            await app.update_settings({"power": {"tdp": 25}})

        assert written_limits(powered)[0] == 20
        assert (await app.settings()).power == Power()
        assert await app.changes() == []
        app.stop()

    asyncio.run(scenario())


@pytest.mark.usefixtures("quick_power")
def test_a_game_start_reaches_the_keeper(
    powered: FakeRoot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    starts: list[PowerKeeper] = []

    def game_started(keeper: PowerKeeper) -> None:
        starts.append(keeper)

    monkeypatch.setattr(PowerKeeper, "game_started", game_started)

    async def scenario() -> None:
        app = make_app(powered, tmp_path)
        await app.start()
        await app.game_started()
        app.stop()

    asyncio.run(scenario())
    assert len(starts) == 1


def test_a_charger_event_has_the_keeper_write_at_once(
    powered: FakeRoot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Without the event the keeper would not look again for a minute.
    monkeypatch.setattr(power_module, "POLL_SECONDS", 60)
    plugged = asyncio.Event()

    async def one_change() -> AsyncGenerator[None]:
        await plugged.wait()
        yield
        await asyncio.Event().wait()

    monkeypatch.setattr(app_module, "supply_changes", one_change)

    async def scenario() -> None:
        app = make_app(powered, tmp_path)
        await app.start()
        await app.update_settings({"power": {"tdp": 20}})
        await asyncio.sleep(0.05)

        powered.write("sys/class/power_supply/AC0/online", 1)
        powered.write(f"{ARMOURY}/ppt_pl1_spl/current_value", 35)
        plugged.set()
        await asyncio.sleep(0.2)

        assert written_limits(powered) == [20, 24, 29]
        app.stop()

    asyncio.run(scenario())


@pytest.mark.usefixtures("quick_power")
def test_origami_keeps_the_tdp_over_steams_slider_while_it_manages_it(
    powered: FakeRoot, tmp_path: Path
) -> None:
    async def scenario() -> None:
        app = make_app(powered, tmp_path)
        await app.start()
        await app.update_settings({"power": {"tdp": 20}})
        await app.set_steam_tdp_limit(on=True)
        await asyncio.sleep(0.05)

        for watts in (12, 15, 22, 18, 25):
            powered.write(f"{ARMOURY}/ppt_pl1_spl/current_value", watts)
            await asyncio.sleep(0.05)
            assert written_limits(powered) == [20, 24, 29]
        assert (await app.power()).contested is False

        # With "Manage TDP" off, the slider sets the TDP.
        await app.update_settings({"manage_tdp": False})
        powered.write(f"{ARMOURY}/ppt_pl1_spl/current_value", 15)
        await asyncio.sleep(0.05)
        assert written_limits(powered)[0] == 15
        app.stop()

    asyncio.run(scenario())


@pytest.mark.usefixtures("quick_power")
def test_a_running_game_gets_its_own_power_while_its_profile_is_active(
    powered: FakeRoot, tmp_path: Path
) -> None:
    game = {"app_id": 1920490, "name": "The Outer Worlds", "power": {"tdp": 13, "headroom": False}}

    async def scenario() -> None:
        app = make_app(powered, tmp_path)
        await app.start()
        await app.update_settings({"power": {"tdp": 20}, "game_power": [game]})
        await asyncio.sleep(0.05)
        assert written_limits(powered) == [20, 24, 29]

        await app.set_game(1920490)
        await asyncio.sleep(0.05)
        # The firmware keeps the short limits above its minimums.
        assert written_limits(powered) == [13, 13, 19]

        # Back on the general settings, the profile waits.
        await app.update_settings({"game_power": [{**game, "active": False}]})
        await asyncio.sleep(0.05)
        assert written_limits(powered) == [20, 24, 29]

        await app.update_settings({"game_power": [game]})
        await app.set_game(None)
        await asyncio.sleep(0.05)
        assert written_limits(powered) == [20, 24, 29]
        app.stop()

    asyncio.run(scenario())


def test_new_settings_reach_the_hardware_before_the_next_look(
    powered: FakeRoot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Without being woken the keeper would not look again for a minute.
    monkeypatch.setattr(power_module, "POLL_SECONDS", 60)

    async def scenario() -> None:
        app = make_app(powered, tmp_path)
        await app.start()
        await asyncio.sleep(0.05)

        await app.update_settings({"power": {"tdp": 25}})
        await asyncio.sleep(0.05)

        assert written_limits(powered) == [25, 29, 34]
        app.stop()

    asyncio.run(scenario())


@pytest.mark.usefixtures("quick_power")
def test_restoring_everything_gives_the_power_fans_and_gyroscope_back(
    powered: FakeRoot,
    fan_curves: Path,
    tmp_path: Path,
    inputplumber: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boost = powered.path / "sys/devices/system/cpu/cpufreq/boost"
    given_back: list[Path] = []

    def reset(root: Path) -> bool:
        given_back.append(root)
        return True

    monkeypatch.setattr(app_module, "reset_to_profile", reset)

    async def scenario() -> None:
        app = make_app(powered, tmp_path)
        await app.start()
        await app.update_settings(
            {"power": {"tdp": 20, "cpu_boost": True}, "fans": {"enabled": True}, "gyro_fix": True}
        )
        await asyncio.sleep(0.05)
        assert boost.read_text(encoding="utf-8") == "1\n"

        await app.restore_all()

        assert given_back == [powered.path]
        assert boost.read_text(encoding="utf-8") == "0\n"
        assert fan_mode(fan_curves) == [2, 2]
        assert not (powered.path / gyro_module.OVERRIDE).exists()
        assert inputplumber == ["inputplumber"] * 2
        assert await app.changes() == []
        # Nothing comes back: Steam sets the TDP, and the boost is the system's.
        await asyncio.sleep(0.05)
        assert (await app.power()).limits is None
        assert boost.read_text(encoding="utf-8") == "0\n"
        assert fan_mode(fan_curves) == [2, 2]
        app.stop()

    asyncio.run(scenario())


@pytest.mark.usefixtures("quick_power")
def test_after_restoring_the_cpu_cap_is_left_to_the_system(
    powered: FakeRoot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    caps: list[Path] = []

    async def program(root: Path) -> None:
        caps.append(root)

    def reset(_root: Path) -> bool:
        return True

    monkeypatch.setattr(app_module, "program_cap", program)
    monkeypatch.setattr(app_module, "reset_to_profile", reset)

    async def scenario() -> None:
        app = make_app(powered, tmp_path)
        await app.start()
        await app.update_settings({"power": {"cpu_boost": False}})
        await asyncio.sleep(0.05)
        caps.clear()

        await app.restore_all()
        await asyncio.sleep(0.05)

        # Neither the TDP nor the boost is ORIGAMI's now, so the cap is not ORIGAMI's either.
        assert caps == []
        app.stop()

    asyncio.run(scenario())


def test_restoring_everything_gives_the_controller_and_screen_back_and_unsets_the_fixes(
    ally_x: FakeRoot,
    tmp_path: Path,
    sent_lighting: list[Lighting],
    sent_vibration: list[Vibration],
    screen: dict[str, list[int] | int],
) -> None:
    # Left by the glow in sleep, a switch of an older version: nothing gives it back.
    journal = tmp_path / "data" / "changes.json"
    journal.parent.mkdir(parents=True)
    journal.write_text(
        json.dumps(
            {
                "version": 1,
                "changes": [{"module": "lighting", "key": "sleep_animation", "original": 0}],
            }
        ),
        encoding="utf-8",
    )

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()
        await app.update_settings(
            {
                "language": "ru",
                "power": {"tdp": 20},
                "lighting": RAINBOW,
                "vibration": {"left": 25, "right": 75},
                "saturation": 150,
                "qam_assist": True,
                "armoury_crate": "origami",
            }
        )

        settings = await app.restore_all()

        assert settings == Settings(
            language=Language.RU, vibration=None, manage_tdp=None, power=Power(tdp=20)
        )
        assert SettingsStore(tmp_path / "settings" / "settings.json").load() == settings
        assert sent_lighting[-1] == CONTROLLER_LIGHTING
        # The driver held 50 / 50 before ORIGAMI.
        assert sent_vibration[-1] == Vibration(left=50, right=50)
        assert screen["written"] == [150, 100]
        assert await app.changes() == []
        app.stop()

    asyncio.run(scenario())


@pytest.mark.usefixtures("quick_power")
def test_restoring_leaves_the_power_and_fans_another_plugin_drives_now(
    powered: FakeRoot, fan_curves: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    boost = powered.path / "sys/devices/system/cpu/cpufreq/boost"
    given_back: list[Path] = []

    def reset(root: Path) -> bool:
        given_back.append(root)
        return True

    monkeypatch.setattr(app_module, "reset_to_profile", reset)
    owner = next(plugin for plugin in POWER_OWNERS if plugin in FAN_OWNERS)

    async def scenario() -> None:
        app = make_app(powered, tmp_path)
        await app.start()
        await app.update_settings({"power": {"tdp": 20, "cpu_boost": True}})
        await app.update_settings({"fans": {"enabled": True}})
        await asyncio.sleep(0.05)
        install_plugin(tmp_path, owner)

        await app.restore_all()

        # The other plugin's TDP, boost and fan curve stay; ORIGAMI only forgets its own.
        assert given_back == []
        assert boost.read_text(encoding="utf-8") == "1\n"
        assert fan_mode(fan_curves) == [1, 1]
        assert await app.changes() == []
        app.stop()

    asyncio.run(scenario())


def test_restoring_leaves_what_another_plugin_drives_now(
    ally_x: FakeRoot,
    tmp_path: Path,
    sent_lighting: list[Lighting],
    screen: dict[str, list[int] | int],
) -> None:
    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()
        await app.update_settings({"lighting": RAINBOW, "saturation": 150})
        install_plugin(tmp_path, LIGHTING_OWNERS[0])
        install_plugin(tmp_path, SATURATION_OWNERS[0])

        await app.restore_all()

        assert sent_lighting == [Lighting.from_json(RAINBOW)]
        assert screen["written"] == [150]
        assert await app.changes() == []

    asyncio.run(scenario())
