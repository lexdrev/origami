# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

import pytest

from origami import magnifier as magnifier_module
from origami.inputplumber import Profile
from origami.magnifier import ATOM, STICK_AS_MOUSE, Magnifier, with_stick_as_mouse
from origami.proc import CommandError

from fakes import FakeDisplay, FakeRoot

# What Steam writes while Steam + L1 is held, and after (measured on the console).
ONE_AND_A_HALF = 98302
ONE = 65535

DEVICE = "/org/shadowblip/InputPlumber/CompositeDevice0"
OPENGAMEPADUI = "/home/deck/.local/share/opengamepadui/data/gamepad/profiles/global_default.json"
# How InputPlumber writes OpenGamepadUI's profile (GetProfileYaml on the console, shortened).
PROFILE = """version: 1
kind: DeviceProfile
name: OpenGamepadUI Default
mapping:
- name: Keyboard
  source_event:
    gamepad:
      button: Keyboard
  target_events:
  - dbus: ui_osk
"""


class FakeInputPlumber:
    """The built-in controller's device in InputPlumber, with the profile it holds."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.profile = Profile(DEVICE, OPENGAMEPADUI, PROFILE)
        self.loaded: list[str] = []
        monkeypatch.setattr(magnifier_module, "builtin_device", self.builtin_device)
        monkeypatch.setattr(magnifier_module, "current_profile", self.current_profile)
        monkeypatch.setattr(magnifier_module, "profile_path", self.profile_path)
        monkeypatch.setattr(magnifier_module, "load_profile_text", self.load_profile_text)
        monkeypatch.setattr(magnifier_module, "load_profile", self.load_profile)

    def builtin_device(self, _root: Path) -> str:
        return DEVICE

    def current_profile(self, device: str) -> Profile:
        assert device == DEVICE
        return self.profile

    def profile_path(self, _device: str) -> str:
        return self.profile.path

    def load_profile_text(self, device: str, text: str) -> None:
        self.loaded.append(text)
        # Loaded from text, a profile has no file.
        self.profile = Profile(device, "", text)

    def load_profile(self, profile: Profile) -> None:
        self.loaded.append(profile.path)
        self.profile = profile


@pytest.fixture
def inputplumber(monkeypatch: pytest.MonkeyPatch) -> FakeInputPlumber:
    return FakeInputPlumber(monkeypatch)


def test_the_right_stick_is_added_after_the_mapping() -> None:
    assert with_stick_as_mouse(PROFILE) == PROFILE + STICK_AS_MOUSE
    assert (
        with_stick_as_mouse("version: 1\nmapping: []\n")
        == "version: 1\nmapping:\n" + STICK_AS_MOUSE
    )


def test_a_mapping_that_ends_in_an_empty_list_keeps_it() -> None:
    profile = "version: 1\nmapping:\n- name: Nothing\n  target_events: []\n"

    assert with_stick_as_mouse(profile) == profile + STICK_AS_MOUSE


def test_a_profile_with_something_after_its_mapping_is_left_alone() -> None:
    with pytest.raises(ValueError, match="mapping"):
        with_stick_as_mouse("version: 1\nmapping: []\ndescription: Later\n")


def test_one_press_magnifies_with_the_stick_and_the_next_gives_the_profile_back(
    fake_root: FakeRoot, display: FakeDisplay, inputplumber: FakeInputPlumber
) -> None:
    display.properties[ATOM] = ONE
    magnifier = Magnifier(fake_root.path)

    assert magnifier.toggle() is True
    assert display.properties[ATOM] == ONE_AND_A_HALF
    assert inputplumber.loaded == [PROFILE + STICK_AS_MOUSE]

    assert magnifier.toggle() is False
    assert display.properties[ATOM] == ONE
    assert inputplumber.loaded == [PROFILE + STICK_AS_MOUSE, OPENGAMEPADUI]


def test_a_profile_loaded_meanwhile_stays(
    fake_root: FakeRoot, display: FakeDisplay, inputplumber: FakeInputPlumber
) -> None:
    magnifier = Magnifier(fake_root.path)
    magnifier.toggle()
    # OpenGamepadUI loads its profile for a game that starts.
    inputplumber.profile = Profile(DEVICE, "/home/deck/game.json", PROFILE)

    magnifier.close()

    assert display.properties[ATOM] == ONE
    assert inputplumber.loaded == [PROFILE + STICK_AS_MOUSE]


def test_closing_a_magnifier_that_is_off_does_nothing(
    fake_root: FakeRoot, display: FakeDisplay, inputplumber: FakeInputPlumber
) -> None:
    Magnifier(fake_root.path).close()

    assert display.calls == []
    assert inputplumber.loaded == []


def test_no_magnifier_without_gamescope(
    fake_root: FakeRoot, inputplumber: FakeInputPlumber
) -> None:
    magnifier = Magnifier(fake_root.path)

    with pytest.raises(CommandError):
        magnifier.toggle()

    assert inputplumber.loaded == []
    with pytest.raises(CommandError):
        magnifier.toggle()


def test_without_inputplumber_the_next_press_still_switches_off(
    fake_root: FakeRoot,
    display: FakeDisplay,
    inputplumber: FakeInputPlumber,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def gone(_device: str) -> Profile:
        raise CommandError("InputPlumber has no device for the Ally controller")

    monkeypatch.setattr(magnifier_module, "current_profile", gone)
    magnifier = Magnifier(fake_root.path)

    with pytest.raises(CommandError):
        magnifier.toggle()
    assert display.properties[ATOM] == ONE_AND_A_HALF

    assert magnifier.toggle() is False
    assert display.properties[ATOM] == ONE
    assert inputplumber.loaded == []
