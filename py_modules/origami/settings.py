# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass, fields, replace
from enum import StrEnum
from pathlib import Path

from origami.buttons import ButtonAction
from origami.fsutil import atomic_write_text
from origami.jsonio import expect_bool, parse_object
from origami.lighting import Lighting
from origami.saturation import MAX_PERCENT as MAX_SATURATION
from origami.triggers import TriggerRumble
from origami.vibration import Vibration

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

# Keys of Steam's quick access tabs (QuickAccessTab): ORIGAMI's own tab stands before one of them.
SOUNDTRACKS_TAB = 7
FIRST_TAB = -1
"""Position before every other tab."""


class Language(StrEnum):
    AUTO = "auto"
    RU = "ru"
    EN = "en"


@dataclass(frozen=True, slots=True)
class Settings:
    language: Language = Language.AUTO
    qam_tab: bool = True
    """ORIGAMI has its own tab in the quick access menu, besides its place inside Decky."""
    qam_tab_before: int | None = SOUNDTRACKS_TAB
    """Steam tab that ORIGAMI's tab stands before; FIRST_TAB puts it on top, None at the end."""
    qam_assist: bool = False
    """ORIGAMI opens the quick access menu when Steam misses a press of its button (B16)."""
    gyro_fix: bool = False
    """ORIGAMI turns the gyroscope's yaw the right way for Steam (B08)."""
    lighting: Lighting | None = None
    """Lighting of the stick rings; None until the user sets it, so the controller keeps its own."""
    saturation: int | None = None
    """Screen saturation in percent (100 = sRGB); None until the user sets it."""
    vibration: Vibration | None = None
    """Handle vibration strength; None until the user sets it, so the controller keeps its own."""
    trigger_rumble: TriggerRumble | None = None
    """Rumble of the impulse triggers (B19); None until the user chooses, and they stay still."""
    armoury_crate: ButtonAction = ButtonAction.NONE
    """What a short press of the upper left button does; nothing reaches Steam from it (B17)."""
    armoury_crate_hold: ButtonAction = ButtonAction.NONE
    """What holding the upper left button does, besides the L5 Steam gets from it."""

    def updated(self, changes: Mapping[str, object]) -> Settings:
        """Return a copy with the given fields changed; raise ValueError on bad input."""
        parsed: dict[str, object] = {}
        for key, value in changes.items():
            match key:
                case "language":
                    parsed[key] = Language(value)
                case "qam_tab" | "qam_assist" | "gyro_fix":
                    parsed[key] = expect_bool(key, value)
                case "qam_tab_before":
                    parsed[key] = _tab_position(value)
                case "lighting":
                    parsed[key] = None if value is None else Lighting.from_json(value)
                case "saturation":
                    parsed[key] = _saturation(value)
                case "armoury_crate" | "armoury_crate_hold":
                    parsed[key] = ButtonAction(value)
                case "vibration":
                    parsed[key] = None if value is None else Vibration.from_json(value)
                case "trigger_rumble":
                    parsed[key] = None if value is None else TriggerRumble.from_json(value)
                case _:
                    raise ValueError(f"Unknown setting: {key}")
        return replace(self, **parsed)

    def to_json(self) -> dict[str, object]:
        return {
            "version": SCHEMA_VERSION,
            "language": self.language.value,
            "qam_tab": self.qam_tab,
            "qam_tab_before": self.qam_tab_before,
            "qam_assist": self.qam_assist,
            "gyro_fix": self.gyro_fix,
            "lighting": None if self.lighting is None else self.lighting.to_json(),
            "saturation": self.saturation,
            "vibration": None if self.vibration is None else self.vibration.to_json(),
            "trigger_rumble": (
                None if self.trigger_rumble is None else self.trigger_rumble.to_json()
            ),
            "armoury_crate": self.armoury_crate.value,
            "armoury_crate_hold": self.armoury_crate_hold.value,
        }


def _saturation(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_SATURATION:
        return value
    raise ValueError(f"Saturation must be a percentage from 0 to {MAX_SATURATION}")


def _tab_position(value: object) -> int | None:
    if value is None:
        return None
    # bool is an int in Python; true/false here is a client bug, not a tab key.
    if isinstance(value, int) and not isinstance(value, bool) and value >= FIRST_TAB:
        return value
    raise ValueError(f"Not a quick access tab position: {value!r}")


_FIELDS = frozenset(field.name for field in fields(Settings))


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> Settings:
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return Settings()
        try:
            data = parse_object(text)
            # Keys written by a newer version are skipped, so a downgrade keeps working.
            return Settings().updated({key: data[key] for key in data.keys() & _FIELDS})
        except ValueError as error:
            log.warning("Ignoring unreadable settings in %s: %s", self._path, error)
            return Settings()

    def save(self, settings: Settings) -> None:
        atomic_write_text(self._path, json.dumps(settings.to_json(), indent=2) + "\n")
