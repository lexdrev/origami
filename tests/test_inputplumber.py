# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import json

import pytest

from origami import inputplumber
from origami.inputplumber import SteamChord, press_chord
from origami.proc import CommandError

from fakes import FakeRoot

# What busctl prints on the console (HARDWARE.md); an external gamepad would add CompositeDevice1.
TREE = (
    "/\n/org\n/org/shadowblip\n/org/shadowblip/InputPlumber\n"
    "/org/shadowblip/InputPlumber/CompositeDevice0\n/org/shadowblip/InputPlumber/CompositeDevice1\n"
    "/org/shadowblip/InputPlumber/Manager\n"
)
SOURCES = {
    "/org/shadowblip/InputPlumber/CompositeDevice0": ["/dev/input/event20"],
    "/org/shadowblip/InputPlumber/CompositeDevice1": [
        "/dev/hidraw5",
        "/dev/hidraw6",
        "/dev/input/event3",
    ],
}

type Calls = list[tuple[str, ...]]


@pytest.fixture
def busctl(monkeypatch: pytest.MonkeyPatch) -> Calls:
    calls: Calls = []

    async def run(*args: str) -> str:
        calls.append(args)
        if "tree" in args:
            return TREE
        if "get-property" in args:
            return json.dumps({"type": "as", "data": SOURCES[args[5]]})
        return ""

    monkeypatch.setattr(inputplumber, "run", run)
    return calls


def test_the_chord_goes_to_the_built_in_controller(ally_x: FakeRoot, busctl: Calls) -> None:
    ally_x.ally_controller()  # its configuration interface is /dev/hidraw5

    asyncio.run(press_chord(ally_x.path, SteamChord.SCREENSHOT))

    assert busctl[-1] == (
        "busctl", "--system", "call", "org.shadowblip.InputPlumber",
        "/org/shadowblip/InputPlumber/CompositeDevice1", "org.shadowblip.Input.CompositeDevice",
        "SendButtonChord", "as", "2", "Gamepad:Button:Guide", "Gamepad:Button:RightBumper",
    )  # fmt: skip


def test_steam_x_is_north_as_linux_names_it() -> None:
    assert SteamChord.KEYBOARD.value == ("Gamepad:Button:Guide", "Gamepad:Button:North")


def test_no_chord_without_the_controller(fake_root: FakeRoot, busctl: Calls) -> None:
    with pytest.raises(CommandError, match="controller"):
        asyncio.run(press_chord(fake_root.path, SteamChord.SCREENSHOT))

    assert busctl == []


def test_no_chord_when_inputplumber_does_not_drive_it(
    ally_x: FakeRoot, busctl: Calls, monkeypatch: pytest.MonkeyPatch
) -> None:
    ally_x.ally_controller()
    monkeypatch.setitem(
        SOURCES, "/org/shadowblip/InputPlumber/CompositeDevice1", ["/dev/input/event3"]
    )

    with pytest.raises(CommandError, match="no device"):
        asyncio.run(press_chord(ally_x.path, SteamChord.SCREENSHOT))

    assert not any("call" in call for call in busctl)
