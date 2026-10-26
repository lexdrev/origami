# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""Steam's button chords, pressed through InputPlumber as if on the controller.

InputPlumber shows the Ally's controller to Steam as a Steam Deck, so Steam's own chords with its
button work: Steam + R1 takes a screenshot, Steam + X shows the keyboard in a game.
SendButtonChord presses the buttons 80 ms apart and lets them go in reverse; SendEvent, which could
hold a button down, panics in InputPlumber 0.83.0 (it blocks inside its async runtime).

InputPlumber names the face buttons as Linux does, where BTN_X is BTN_NORTH: X is North, Y West.
"""

import asyncio
import re
from enum import Enum
from pathlib import Path

from origami.controller import CONFIG_INTERFACE, find_hidraw
from origami.jsonio import parse_object
from origami.proc import CommandError, run

SERVICE = "org.shadowblip.InputPlumber"
COMPOSITE_DEVICE = "org.shadowblip.Input.CompositeDevice"
COMPOSITE_PATH = re.compile(r"^/org/shadowblip/InputPlumber/CompositeDevice\d+$", re.MULTILINE)
TIMEOUT_SECONDS = 5
STEAM = "Gamepad:Button:Guide"


class SteamChord(Enum):
    SCREENSHOT = (STEAM, "Gamepad:Button:RightBumper")
    KEYBOARD = (STEAM, "Gamepad:Button:North")


async def press_chord(root: Path, chord: SteamChord) -> None:
    """Press a chord on the built-in controller; raise CommandError or TimeoutError on failure."""
    async with asyncio.timeout(TIMEOUT_SECONDS):
        device = await _builtin_device(root)
        buttons = chord.value
        await run(
            "busctl",
            "--system",
            "call",
            SERVICE,
            device,
            COMPOSITE_DEVICE,
            "SendButtonChord",
            "as",
            str(len(buttons)),
            *buttons,
        )


async def _builtin_device(root: Path) -> str:
    """InputPlumber's device for the built-in controller: the one fed by its configuration node.

    Its number changes when InputPlumber restarts, and an external gamepad gets a device of its own.
    """
    config = await asyncio.to_thread(find_hidraw, root, CONFIG_INTERFACE)
    if config is None:
        raise CommandError("The Ally controller is not there")
    tree = await run("busctl", "--system", "--list", "tree", SERVICE)
    for path in COMPOSITE_PATH.findall(tree):
        sources = await run(
            "busctl",
            "--system",
            "--json=short",
            "get-property",
            SERVICE,
            path,
            COMPOSITE_DEVICE,
            "SourceDevicePaths",
        )
        if str(Path("/") / config.relative_to(root)) in _strings(sources):
            return path
    raise CommandError("InputPlumber has no device for the Ally controller")


def _strings(output: str) -> list[str]:
    # busctl --json=short prints {"type":"as","data":[...]}.
    try:
        data = parse_object(output).get("data")
    except ValueError:
        return []
    return [item for item in data if isinstance(item, str)] if isinstance(data, list) else []
