# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Buttons, chords, keys and device profiles of the built-in controller, through InputPlumber.

InputPlumber shows the Ally's controller to Steam as a Steam Deck, so Steam's own chords with its
button work: Steam + R1 takes a screenshot, Steam + X shows the keyboard in a game.
SendButtonChord presses the buttons 80 ms apart and lets them go in reverse, so a chord of one
button is a press of 80 ms; SendEvent, which could hold a button down, panics in InputPlumber
0.83.0 (it blocks inside its async runtime).

InputPlumber names the face buttons as Linux does, where BTN_X is BTN_NORTH: X is North, Y West.

Its keyboard is a uinput device, so gamescope takes its keys as a real keyboard's, modifiers
included. The keys Steam presses itself through gamescope lose their modifiers (gamescope 3.17.0):
Ctrl+V from Steam's on-screen keyboard arrives as a plain "v".

The calls block: callers run them in a thread, and the magnifier also makes them while the plugin
unloads, when nothing can be awaited.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from origami.controller import CONFIG_INTERFACE, find_hidraw
from origami.jsonio import JsonValue, parse_object
from origami.proc import CommandError, run_blocking

SERVICE = "org.shadowblip.InputPlumber"
COMPOSITE_DEVICE = "org.shadowblip.Input.CompositeDevice"
COMPOSITE_PATH = re.compile(r"^/org/shadowblip/InputPlumber/CompositeDevice\d+$", re.MULTILINE)
TARGET = "org.shadowblip.Input.Target"
KEYBOARD = "org.shadowblip.Input.Keyboard"
FORCE_FEEDBACK = "org.shadowblip.Output.ForceFeedback"
TIMEOUT_SECONDS = 5
STEAM = "Gamepad:Button:Guide"
PASTE = ("KEY_LEFTCTRL", "KEY_V")


class Chord(Enum):
    SCREENSHOT = (STEAM, "Gamepad:Button:RightBumper")
    KEYBOARD = (STEAM, "Gamepad:Button:North")
    L5 = ("Gamepad:Button:LeftPaddle2",)
    """L5 alone, which InputPlumber's capability map gives the upper left button held."""


@dataclass(frozen=True, slots=True)
class Profile:
    """A device profile as InputPlumber holds it."""

    device: str
    path: str
    """The file it came from; empty when it was loaded from text."""
    text: str
    """The profile in YAML, as InputPlumber writes it."""


def press_chord(root: Path, chord: Chord) -> None:
    """Press a chord on the built-in controller; raise CommandError or TimeoutError on failure."""
    buttons = chord.value
    _call(builtin_device(root), "SendButtonChord", "as", str(len(buttons)), *buttons)


def press_keys(root: Path, keys: Sequence[str]) -> None:
    """Press keys together on the controller's keyboard and let them go in reverse.

    Raise CommandError or TimeoutError on failure; the keys already down go up first.
    """
    keyboard = keyboard_target(builtin_device(root))
    pressed: list[str] = []
    try:
        for key in keys:
            _send_key(keyboard, key, down=True)
            pressed.append(key)
    finally:
        # A key left down would stay held for everything typed after it.
        for key in reversed(pressed):
            _send_key(keyboard, key, down=False)


class NoKeyboardError(CommandError):
    """InputPlumber made no keyboard for the controller, as 0.78 on SteamOS (RC71L report)."""


def keyboard_target(device: str) -> str:
    """The keyboard InputPlumber made for this device, one of its target devices."""
    for target in _strings(_property(device, "TargetDevices")):
        kind = _data(_busctl("--json=short", "get-property", SERVICE, target, TARGET, "DeviceType"))
        if kind == "keyboard":
            return target
    raise NoKeyboardError("InputPlumber has no keyboard for the Ally controller")


def builtin_device(root: Path) -> str:
    """InputPlumber's device for the built-in controller: the one fed by its configuration node.

    Its number changes when InputPlumber restarts, and an external gamepad gets a device of its own.
    """
    config = find_hidraw(root, CONFIG_INTERFACE)
    if config is None:
        raise CommandError("The Ally controller is not there")
    node = str(Path("/") / config.relative_to(root))
    for path in COMPOSITE_PATH.findall(_busctl("--list", "tree", SERVICE)):
        if node in _strings(_property(path, "SourceDevicePaths")):
            return path
    raise CommandError("InputPlumber has no device for the Ally controller")


def start_rumble(device: str, strength: float) -> None:
    """Rumble the controller through InputPlumber as a game does, until stop_rumble.

    The strength runs from 0 to 1, as the speed of both handles in Steam's rumble report; the
    MCU's own strength then scales it. InputPlumber 0.78 and 0.83 have this method.
    """
    _busctl("call", SERVICE, device, FORCE_FEEDBACK, "Rumble", "d", f"{strength:g}")


def stop_rumble(device: str) -> None:
    _busctl("call", SERVICE, device, FORCE_FEEDBACK, "Stop")


def profile_path(device: str) -> str:
    data = _data(_property(device, "ProfilePath"))
    return data if isinstance(data, str) else ""


def current_profile(device: str) -> Profile:
    texts = _strings(_call(device, "GetProfileYaml", json=True))
    if len(texts) != 1:
        raise CommandError("InputPlumber sent no profile")
    return Profile(device, profile_path(device), texts[0])


def load_profile_text(device: str, text: str) -> None:
    _call(device, "LoadProfileFromYaml", "s", text)


def load_profile(profile: Profile) -> None:
    """Load a profile again as it was: from its file, or from its text when it had none."""
    if profile.path:
        _call(profile.device, "LoadProfilePath", "s", profile.path)
    else:
        load_profile_text(profile.device, profile.text)


def _call(device: str, method: str, *args: str, json: bool = False) -> str:
    options = ("--json=short",) if json else ()
    return _busctl(*options, "call", SERVICE, device, COMPOSITE_DEVICE, method, *args)


def _property(device: str, name: str) -> str:
    return _busctl("--json=short", "get-property", SERVICE, device, COMPOSITE_DEVICE, name)


def _send_key(keyboard: str, key: str, *, down: bool) -> None:
    _busctl("call", SERVICE, keyboard, KEYBOARD, "SendKey", "sb", key, "true" if down else "false")


def _busctl(*args: str) -> str:
    return run_blocking("busctl", "--system", *args, timeout=TIMEOUT_SECONDS)


def _data(output: str) -> JsonValue:
    # busctl --json=short prints {"type":"as","data":[...]}, and a call's replies as a list.
    try:
        return parse_object(output).get("data")
    except ValueError:
        return None


def _strings(output: str) -> list[str]:
    data = _data(output)
    return [item for item in data if isinstance(item, str)] if isinstance(data, list) else []
