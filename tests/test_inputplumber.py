# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

import json

import pytest

from origami import inputplumber
from origami.inputplumber import (
    PASTE,
    Chord,
    Profile,
    current_profile,
    load_profile,
    load_profile_text,
    press_chord,
    press_keys,
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
KEYBOARD = "/org/shadowblip/InputPlumber/devices/target/keyboard0"
# The targets InputPlumber makes for the built-in controller (seen on the console 2026-11-01).
TARGETS = {
    DEVICE: [
        "/org/shadowblip/InputPlumber/devices/target/mouse0",
        "/org/shadowblip/InputPlumber/devices/target/gamepad1",
        KEYBOARD,
    ]
}
KINDS = {
    "/org/shadowblip/InputPlumber/devices/target/mouse0": "mouse",
    "/org/shadowblip/InputPlumber/devices/target/gamepad1": "deck-uhid",
    KEYBOARD: "keyboard",
}
OPENGAMEPADUI = "/home/deck/.local/share/opengamepadui/data/gamepad/profiles/global_default.json"
PROFILE = "version: 1\nkind: DeviceProfile\nname: OpenGamepadUI Default\nmapping: []\n"

type Calls = list[tuple[str, ...]]


def property_value(path: str, name: str) -> str | list[str]:
    by_path = {"SourceDevicePaths": SOURCES, "TargetDevices": TARGETS, "DeviceType": KINDS}
    return by_path[name][path] if name in by_path else OPENGAMEPADUI


@pytest.fixture
def busctl(monkeypatch: pytest.MonkeyPatch) -> Calls:
    calls: Calls = []

    def run_blocking(*args: str, timeout: float) -> str:
        assert timeout > 0
        calls.append(args)
        if "tree" in args:
            return TREE
        if "get-property" in args:
            value = property_value(args[5], args[-1])
            return json.dumps({"type": "as" if isinstance(value, list) else "s", "data": value})
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


def sent_keys(calls: Calls) -> list[tuple[str, ...]]:
    return [call[-2:] for call in calls if "SendKey" in call]


def test_paste_is_ctrl_v_on_the_keyboard_of_the_built_in_controller(
    ally_x: FakeRoot, busctl: Calls
) -> None:
    ally_x.ally_controller()

    press_keys(ally_x.path, PASTE)

    assert sent_keys(busctl) == [
        ("KEY_LEFTCTRL", "true"),
        ("KEY_V", "true"),
        ("KEY_V", "false"),
        ("KEY_LEFTCTRL", "false"),
    ]
    assert {call[4] for call in busctl if "SendKey" in call} == {KEYBOARD}


def test_a_key_already_down_goes_up_when_the_next_one_fails(
    ally_x: FakeRoot, busctl: Calls, monkeypatch: pytest.MonkeyPatch
) -> None:
    ally_x.ally_controller()
    answer = inputplumber.run_blocking

    def run_blocking(*args: str, timeout: float) -> str:
        if args[-2:] == ("KEY_V", "true"):
            raise CommandError("InputPlumber did not answer")
        return answer(*args, timeout=timeout)

    monkeypatch.setattr(inputplumber, "run_blocking", run_blocking)

    with pytest.raises(CommandError):
        press_keys(ally_x.path, PASTE)

    assert sent_keys(busctl) == [("KEY_LEFTCTRL", "true"), ("KEY_LEFTCTRL", "false")]


def test_no_keys_when_inputplumber_made_no_keyboard(
    ally_x: FakeRoot, busctl: Calls, monkeypatch: pytest.MonkeyPatch
) -> None:
    ally_x.ally_controller()
    monkeypatch.setitem(TARGETS, DEVICE, TARGETS[DEVICE][:2])

    with pytest.raises(CommandError, match="no keyboard"):
        press_keys(ally_x.path, PASTE)

    assert sent_keys(busctl) == []


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
