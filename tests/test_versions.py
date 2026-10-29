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
            "OSTREE_VERSION='44.20261023'",
            r'PRETTY_NAME="Say \"hi\" \$HOME"',
            "",
            "not a field",
            "BAD KEY=1",
        ]
    )

    assert parse_os_release(text) == {
        "NAME": "Bazzite",
        "ID": "bazzite",
        "OSTREE_VERSION": "44.20261023",
        "PRETTY_NAME": 'Say "hi" $HOME',
    }


def test_etc_takes_precedence_over_usr_lib(ally_x: FakeRoot) -> None:
    ally_x.write("etc/os-release", 'NAME="Custom"\nVERSION_ID=1')

    expected = OsRelease(name="Custom", version_id="1", image_version=None)

    assert read_os_release(ally_x.path) == expected


def test_versions(ally_x: FakeRoot, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []

    async def fake_run(*args: str) -> str:
        calls.append(args)
        return '{"type":"s","data":"0.83.0"}\n'

    monkeypatch.setattr(versions, "run", fake_run)

    result = asyncio.run(read_versions(ally_x.path, decky="v3.3.0"))

    assert result == Versions(
        os=OsRelease(name="Bazzite", version_id="44", image_version="44.20261023"),
        kernel="7.2.9-ogc3.1.fc44.x86_64",
        inputplumber="0.83.0",
        decky="v3.3.0",
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
