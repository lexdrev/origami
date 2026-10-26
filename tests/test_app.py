# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import os
from pathlib import Path

import pytest

from origami import app as app_module
from origami import versions
from origami.app import QAM_PRESSED, Emit, Origami
from origami.settings import Language, Settings

from fakes import FakeRoot


@pytest.fixture(autouse=True)
def no_busctl(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run(*_args: str) -> str:
        return '{"type":"s","data":"0.83.0"}'

    monkeypatch.setattr(versions, "run", fake_run)


async def no_events(_event: str) -> None:
    pass


def make_app(root: FakeRoot, tmp_path: Path, emit: Emit = no_events) -> Origami:
    return Origami(
        root=root.path,
        settings_dir=tmp_path / "settings",
        data_dir=tmp_path / "data",
        version="0.1.0",
        decky_version="v3.3.0",
        emit=emit,
    )


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

        async def emit(event: str) -> None:
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

        await app.stop()
        os.close(writer)

    asyncio.run(scenario())


def test_qam_assist_starts_with_the_plugin_when_it_was_on(ally_x: FakeRoot, tmp_path: Path) -> None:
    press = bytes.fromhex("5a9300000000")
    node = ally_x.hidraw(5, driver="asus_rog_ally", phys="usb-0000:66:00.0-4/input2")

    async def scenario() -> None:
        events: list[str] = []
        received = asyncio.Event()

        async def emit(event: str) -> None:
            events.append(event)
            received.set()

        first = make_app(ally_x, tmp_path)
        await first.start()
        await first.update_settings({"qam_assist": True})
        await first.stop()

        writer = os.open(node, os.O_RDWR | os.O_NONBLOCK)
        app = make_app(ally_x, tmp_path, emit)
        await app.start()
        await asyncio.sleep(0.05)
        os.write(writer, press)
        async with asyncio.timeout(1):
            await received.wait()
        assert events == [QAM_PRESSED]
        await app.stop()
        os.close(writer)

    asyncio.run(scenario())
