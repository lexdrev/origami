# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""Rumble of the impulse triggers (BUGS.md, B19).

The Ally X has a motor in each trigger, but InputPlumber 0.83 sends them nothing: its rumble report
always carries 0 for both. The rumble program (origami.rumble) fills each chosen trigger from the
grip motor on its side as the report goes out, at the level chosen here. Games rumble the grips, so
a trigger follows a game and nothing else.

The trigger motors answer in a narrow band (HARDWARE.md): up to about 30 they hum in the shell, and
only 60 and more are felt in the finger. A game's shots give a grip 60-90% of its full strength, so
the levels are four points of that band rather than a fine scale whose steps feel the same.
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

from origami.controller import GAMEPAD_INTERFACE, find_hid_device, rumble
from origami.jsonio import JsonValue, expect_bool
from origami.rumble import lays_out_rumble

BOARDS = frozenset({"RC73XA"})
"""Boards with motors in the triggers."""


class Triggers(StrEnum):
    RIGHT = "right"
    BOTH = "both"


class TriggerLevel(StrEnum):
    SOFT = "soft"
    MEDIUM = "medium"
    STRONG = "strong"
    MAX = "max"


LEVEL_STRENGTH = {
    TriggerLevel.SOFT: 30,
    TriggerLevel.MEDIUM: 60,
    TriggerLevel.STRONG: 80,
    TriggerLevel.MAX: 100,
}
"""Strength of a trigger at a game's full rumble, in percent, for each level."""


class TriggerState(StrEnum):
    UNAVAILABLE = "unavailable"
    """The console has no trigger motors, or its controller lays out the rumble report otherwise."""
    AVAILABLE = "available"


@dataclass(frozen=True, slots=True)
class TriggerRumble:
    enabled: bool = False
    """Off keeps the trigger motors still; the triggers and the level wait until it is on again."""
    triggers: Triggers = Triggers.RIGHT
    level: TriggerLevel = TriggerLevel.MEDIUM

    @classmethod
    def from_json(cls, value: object) -> TriggerRumble:
        """Parse trigger rumble sent by the frontend or saved; raise ValueError on bad input."""
        if not isinstance(value, dict):
            raise ValueError("trigger rumble must be an object")
        data = cast("dict[str, object]", value)
        defaults = cls()
        triggers = data.get("triggers", defaults.triggers)
        # Saved before the switch: then "off" was one of the triggers, and the others meant on.
        if "enabled" not in data and "triggers" in data:
            data = {**data, "enabled": triggers != "off"}
            triggers = defaults.triggers if triggers == "off" else triggers
        return cls(
            enabled=expect_bool("enabled", data.get("enabled", defaults.enabled)),
            triggers=Triggers(triggers),
            level=TriggerLevel(data.get("level", defaults.level)),
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {"enabled": self.enabled, "triggers": self.triggers.value, "level": self.level.value}

    def strengths(self) -> tuple[int, int]:
        """Strength of the left and the right trigger at a game's full rumble; 0 keeps it still."""
        if not self.enabled:
            return 0, 0
        strength = LEVEL_STRENGTH[self.level]
        return (strength if self.triggers is Triggers.BOTH else 0), strength


def read_trigger_state(root: Path, board: str | None) -> TriggerState:
    if board not in BOARDS:
        return TriggerState.UNAVAILABLE
    device = find_hid_device(root, GAMEPAD_INTERFACE)
    if device is None or not lays_out_rumble(device.path):
        return TriggerState.UNAVAILABLE
    return TriggerState.AVAILABLE


def pulse_report(trigger_rumble: TriggerRumble) -> bytes:
    """The triggers at their strength and the grips still; the program keeps such triggers."""
    left, right = trigger_rumble.strengths()
    return bytes([0x0D, 0x0F, left, right, 0, 0, 0xFF, 0x00, 0xEB])


def start_trigger_pulse(root: Path, trigger_rumble: TriggerRumble) -> None:
    """Rumble the triggers as a game's full rumble would, until stop_rumble."""
    rumble(root, pulse_report(trigger_rumble))
