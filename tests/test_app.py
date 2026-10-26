# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from pathlib import Path

import pytest

from origami import app as app_module
from origami import versions
from origami.app import Origami
from origami.settings import Language, Settings

from fakes import FakeRoot


@pytest.fixture(autouse=True)
def no_busctl(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run(*_args: str) -> str:
        return '{"type":"s","data":"0.83.0"}'

    monkeypatch.setattr(versions, "run", fake_run)


def make_app(root: FakeRoot, tmp_path: Path) -> Origami:
    return Origami(
        root=root.path,
        settings_dir=tmp_path / "settings",
        data_dir=tmp_path / "data",
        version="0.1.0",
        decky_version="v3.3.0",
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
