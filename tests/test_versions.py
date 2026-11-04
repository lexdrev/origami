# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio

import pytest

from origami import versions
from origami.proc import CommandError
from origami.versions import OsRelease, Versions, parse_os_release, read_os_release, read_versions

from fakes import FakeRoot


def test_os_release_quoting() -> None:
    text = "\n".join(
        [
            "# comment",
            'NAME="Bazzite"',
            "ID=bazzite",
            "OSTREE_VERSION='45.20261104'",
            r'PRETTY_NAME="Say \"hi\" \$HOME"',
            "",
            "not a field",
            "BAD KEY=1",
        ]
    )

    assert parse_os_release(text) == {
        "NAME": "Bazzite",
        "ID": "bazzite",
        "OSTREE_VERSION": "45.20261104",
        "PRETTY_NAME": 'Say "hi" $HOME',
    }


def test_etc_takes_precedence_over_usr_lib(ally_x: FakeRoot) -> None:
    ally_x.write("etc/os-release", 'NAME="Custom"\nVERSION_ID=1')

    expected = OsRelease(id=None, name="Custom", version_id="1", image_version=None, build_id=None)

    assert read_os_release(ally_x.path) == expected


def test_steamos_keeps_its_build_apart(ally_x: FakeRoot) -> None:
    ally_x.write(
        "etc/os-release", 'NAME="SteamOS"\nID=steamos\nVERSION_ID=3.9.5\nBUILD_ID=20261023.100'
    )

    expected = OsRelease(
        id="steamos",
        name="SteamOS",
        version_id="3.9.5",
        image_version=None,
        build_id="20261023.100",
    )

    assert read_os_release(ally_x.path) == expected


def test_versions(ally_x: FakeRoot, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []

    async def fake_run(*args: str) -> str:
        calls.append(args)
        return '{"type":"s","data":"0.83.1"}\n'

    monkeypatch.setattr(versions, "run", fake_run)

    result = asyncio.run(read_versions(ally_x.path, decky="v3.3.1"))

    assert result == Versions(
        os=OsRelease(
            id="bazzite",
            name="Bazzite",
            version_id="45",
            image_version="45.20261104",
            build_id="Stable (F45.20261104)",
        ),
        kernel="7.2.15-ogc1.1.fc45.x86_64",
        inputplumber="0.83.1",
        decky="v3.3.1",
    )
    # Interface name checked on the console with busctl introspect (InputPlumber 0.83.0).
    assert calls[0][0] == "busctl"
    assert "org.shadowblip.InputManager" in calls[0]


@pytest.mark.parametrize("outcome", [CommandError("busctl exited with 1"), "[]", "garbage"])
def test_inputplumber_version_is_optional(
    monkeypatch: pytest.MonkeyPatch, outcome: CommandError | str
) -> None:
    async def fake_run(*_args: str) -> str:
        if isinstance(outcome, CommandError):
            raise outcome
        return outcome

    monkeypatch.setattr(versions, "run", fake_run)

    assert asyncio.run(versions.read_inputplumber_version()) is None
