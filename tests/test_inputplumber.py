# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import json

import pytest

from origami import inputplumber
from origami.inputplumber import (
    Chord,
    Profile,
    current_profile,
    load_profile,
    load_profile_text,
    press_chord,
)
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
DEVICE = "/org/shadowblip/InputPlumber/CompositeDevice1"
OPENGAMEPADUI = "/home/deck/.local/share/opengamepadui/data/gamepad/profiles/global_default.json"
PROFILE = "version: 1\nkind: DeviceProfile\nname: OpenGamepadUI Default\nmapping: []\n"

type Calls = list[tuple[str, ...]]


@pytest.fixture
def busctl(monkeypatch: pytest.MonkeyPatch) -> Calls:
    calls: Calls = []

    def run_blocking(*args: str, timeout: float) -> str:
        assert timeout > 0
        calls.append(args)
        if "tree" in args:
            return TREE
        if "SourceDevicePaths" in args:
            return json.dumps({"type": "as", "data": SOURCES[args[5]]})
        if "ProfilePath" in args:
            return json.dumps({"type": "s", "data": OPENGAMEPADUI})
        if "GetProfileYaml" in args:
            return json.dumps({"type": "s", "data": [PROFILE]})
        return ""

    monkeypatch.setattr(inputplumber, "run_blocking", run_blocking)
    return calls


def test_the_chord_goes_to_the_built_in_controller(ally_x: FakeRoot, busctl: Calls) -> None:
    ally_x.ally_controller()  # its configuration interface is /dev/hidraw5

    press_chord(ally_x.path, Chord.SCREENSHOT)

    assert busctl[-1] == (
        "busctl", "--system", "call", "org.shadowblip.InputPlumber", DEVICE,
        "org.shadowblip.Input.CompositeDevice",
        "SendButtonChord", "as", "2", "Gamepad:Button:Guide", "Gamepad:Button:RightBumper",
    )  # fmt: skip


def test_steam_x_is_north_as_linux_names_it() -> None:
    assert Chord.KEYBOARD.value == ("Gamepad:Button:Guide", "Gamepad:Button:North")


def test_l5_is_the_paddle_the_held_armoury_crate_button_gives() -> None:
    # InputPlumber's capability map aly2 turns the held button (F21) into LeftPaddle2.
    assert Chord.L5.value == ("Gamepad:Button:LeftPaddle2",)


def test_no_chord_without_the_controller(fake_root: FakeRoot, busctl: Calls) -> None:
    with pytest.raises(CommandError, match="controller"):
        press_chord(fake_root.path, Chord.SCREENSHOT)

    assert busctl == []


def test_no_chord_when_inputplumber_does_not_drive_it(
    ally_x: FakeRoot, busctl: Calls, monkeypatch: pytest.MonkeyPatch
) -> None:
    ally_x.ally_controller()
    monkeypatch.setitem(SOURCES, DEVICE, ["/dev/input/event3"])

    with pytest.raises(CommandError, match="no device"):
        press_chord(ally_x.path, Chord.SCREENSHOT)

    assert not any("call" in call for call in busctl)


@pytest.mark.usefixtures("busctl")
def test_the_profile_is_read_with_the_file_it_came_from() -> None:
    assert current_profile(DEVICE) == Profile(DEVICE, OPENGAMEPADUI, PROFILE)


def test_a_profile_goes_back_from_its_file_or_else_from_its_text(busctl: Calls) -> None:
    load_profile(Profile(DEVICE, OPENGAMEPADUI, PROFILE))
    load_profile(Profile(DEVICE, "", PROFILE))
    load_profile_text(DEVICE, PROFILE)

    method_and_value = [call[-3:] for call in busctl]
    assert method_and_value == [
        ("LoadProfilePath", "s", OPENGAMEPADUI),
        ("LoadProfileFromYaml", "s", PROFILE),
        ("LoadProfileFromYaml", "s", PROFILE),
    ]
