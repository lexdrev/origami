# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import json
import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest

from origami import app as app_module
from origami import versions
from origami.app import BUTTON_ACTION, QAM_PRESSED, Emit, Environment, Origami
from origami.buttons import ButtonAction
from origami.inputplumber import SteamChord
from origami.journal import Change
from origami.jsonio import JsonValue
from origami.lighting import Lighting, LightMode
from origami.settings import Language, Settings
from origami.vibration import Vibration

from fakes import FakeRoot


@pytest.fixture(autouse=True)
def no_busctl(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run(*_args: str) -> str:
        return '{"type":"s","data":"0.83.0"}'

    monkeypatch.setattr(versions, "run", fake_run)


async def no_events(_event: str, *_args: JsonValue) -> None:
    pass


def make_app(root: FakeRoot, tmp_path: Path, emit: Emit = no_events) -> Origami:
    environment = Environment(
        root=root.path,
        settings_dir=tmp_path / "settings",
        data_dir=tmp_path / "data",
        decky_home=tmp_path / "decky",
        version="0.1.0",
        decky_version="v3.3.0",
    )
    return Origami(environment, emit=emit)


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

        assert await pending == Settings()

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
        assert await app.update_settings({"language": "en"}) == Settings(language=Language.EN)

        restarted = make_app(ally_x, tmp_path)
        await restarted.start()
        assert await restarted.settings() == Settings(language=Language.EN)

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
        assert (await app.settings()).qam_assist is False

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


def test_lighting_is_left_alone_while_huesync_runs(
    ally_x: FakeRoot, tmp_path: Path, sent_lighting: list[Lighting]
) -> None:
    install_plugin(tmp_path, "HueSync")

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()
        assert (await app.conflicts()).lighting == "HueSync"

        with pytest.raises(RuntimeError, match="HueSync"):
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


def test_vibrantdeck_owns_the_saturation(ally_x: FakeRoot, tmp_path: Path) -> None:
    install_plugin(tmp_path, "vibrantDeck")

    conflicts = asyncio.run(make_app(ally_x, tmp_path).conflicts())

    assert (conflicts.lighting, conflicts.saturation) == (None, "vibrantDeck")


@pytest.mark.parametrize("plugin", ["Ally Vibe Control", "Ally Fix"])
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


def test_saturation_is_left_alone_while_vibrantdeck_runs(
    ally_x: FakeRoot, tmp_path: Path, screen: dict[str, list[int] | int]
) -> None:
    install_plugin(tmp_path, "vibrantDeck")

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()

        with pytest.raises(RuntimeError, match="vibrantDeck"):
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


def test_vibration_is_left_alone_while_ally_vibe_control_runs(
    ally_x: FakeRoot, tmp_path: Path, sent_vibration: list[Vibration]
) -> None:
    install_plugin(tmp_path, "Ally Vibe Control")

    async def scenario() -> None:
        app = make_app(ally_x, tmp_path)
        await app.start()

        with pytest.raises(RuntimeError, match="Ally Vibe Control"):
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

        assert (settings.armoury_crate, settings.armoury_crate_hold) == (ButtonAction.NONE,) * 2
        assert not any(task.get_name() == "origami-buttons" for task in asyncio.all_tasks())

    asyncio.run(scenario())


def test_steam_chords_are_pressed_and_other_actions_go_to_the_frontend(
    ally_x: FakeRoot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    short_press = bytes.fromhex("5aa600000000")
    pressed: list[SteamChord] = []

    async def press(_root: Path, chord: SteamChord) -> None:
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
        assert pressed == [SteamChord.SCREENSHOT]
        assert events.empty()

        await app.update_settings({"armoury_crate": "overlay"})
        os.write(writer, short_press)
        assert await asyncio.wait_for(events.get(), 1) == (BUTTON_ACTION, "overlay")
        assert pressed == [SteamChord.SCREENSHOT]

        app.stop()
        os.close(writer)

    asyncio.run(scenario())


def test_the_magnifier_is_switched_through_gamescope(
    ally_x: FakeRoot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    switched: list[Path] = []

    async def toggle(root: Path) -> bool:
        switched.append(root)
        return True

    monkeypatch.setattr(app_module, "toggle_magnifier", toggle)

    async def scenario() -> None:
        config = ally_x.ally_controller()
        writer = os.open(config, os.O_RDWR | os.O_NONBLOCK)
        app = make_app(ally_x, tmp_path)
        await app.start()
        await app.update_settings({"armoury_crate": "magnifier"})
        await asyncio.sleep(0.05)

        os.write(writer, bytes.fromhex("5aa600000000"))
        await asyncio.sleep(0.05)

        assert switched == [ally_x.path]
        app.stop()
        os.close(writer)

    asyncio.run(scenario())
