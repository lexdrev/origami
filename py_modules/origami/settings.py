# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, replace
from enum import StrEnum
from pathlib import Path
from typing import cast

from origami.buttons import ButtonAction
from origami.fans import FanCurve
from origami.fsutil import atomic_write_text
from origami.jsonio import expect_bool, parse_object
from origami.lighting import Lighting
from origami.power import GamePower, Power
from origami.saturation import MAX_PERCENT as MAX_SATURATION
from origami.triggers import TriggerRumble
from origami.vibration import Vibration

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

MAX_GAME_PROFILES = 200

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
    # Fixes of system bugs are None until the user sets them: off all the same, but the screens show
    # them as problems until then. Switched off by hand, they are the user's choice.
    qam_assist: bool | None = None
    """ORIGAMI opens the quick access menu when Steam misses a press of its button (B16)."""
    gyro_fix: bool | None = None
    """ORIGAMI turns the gyroscope's yaw the right way for Steam (B08)."""
    lighting: Lighting | None = None
    """Lighting of the stick rings; None until the user sets it, so the controller keeps its own."""
    saturation: int | None = None
    """Screen saturation in percent (100 = sRGB); None until the user sets it."""
    vibration: Vibration | None = field(default_factory=Vibration)
    """Handle vibration strength, the middle level from the first start: the controller's own 100%
    is too strong. None leaves the controller's own, as settings saved before this default do."""
    trigger_rumble: TriggerRumble | None = None
    """Rumble of the impulse triggers (B19); None until the user chooses, and they stay still."""
    armoury_crate: ButtonAction | None = None
    """What a short press of the upper left button does; nothing reaches Steam from it (B17).
    None until the user sets it, and nothing then too."""
    armoury_crate_hold: ButtonAction | None = None
    """What holding the upper left button does, besides the L5 Steam gets from it."""
    manage_tdp: bool = True
    """ORIGAMI owns the TDP and writes it again whenever it drops (B04, B05); off, Steam sets it."""
    power: Power = field(default_factory=Power)
    """TDP, its headroom and the CPU boost; the factory's limits until the user changes them."""
    battery_high_tdp: bool = False
    """The TDP may go over 25 W on the battery too."""
    game_power: tuple[GamePower, ...] = ()
    """Games with power settings of their own, one profile each."""
    fans: FanCurve | None = None
    """ORIGAMI's curve for both fans (B07); None until switched on: the firmware's own."""

    def power_for(self, game: int | None) -> Power:
        """The power a game runs with: its own profile while that is active, else the general."""
        for profile in self.game_power:
            if profile.app_id == game and profile.active:
                return profile.power
        return self.power

    def updated(self, changes: Mapping[str, object]) -> Settings:
        """Return a copy with the given fields changed; raise ValueError on bad input."""
        parsed: dict[str, object] = {}
        for key, value in changes.items():
            match key:
                case "language":
                    parsed[key] = Language(value)
                case "qam_tab" | "manage_tdp" | "battery_high_tdp":
                    parsed[key] = expect_bool(key, value)
                case "qam_assist" | "gyro_fix":
                    parsed[key] = None if value is None else expect_bool(key, value)
                case "qam_tab_before":
                    parsed[key] = _tab_position(value)
                case "lighting" | "vibration" | "trigger_rumble" | "fans":
                    parsed[key] = None if value is None else _OPTIONAL[key].from_json(value)
                case "saturation":
                    parsed[key] = _saturation(value)
                case "armoury_crate":
                    parsed[key] = None if value is None else ButtonAction(value)
                case "armoury_crate_hold":
                    parsed[key] = None if value is None else _hold_action(value)
                case "power":
                    parsed[key] = Power.from_json(value)
                case "game_power":
                    parsed[key] = _game_power(value)
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
            "armoury_crate": None if self.armoury_crate is None else self.armoury_crate.value,
            "armoury_crate_hold": (
                None if self.armoury_crate_hold is None else self.armoury_crate_hold.value
            ),
            "manage_tdp": self.manage_tdp,
            "power": self.power.to_json(),
            "battery_high_tdp": self.battery_high_tdp,
            "game_power": [profile.to_json() for profile in self.game_power],
            "fans": None if self.fans is None else self.fans.to_json(),
        }


_OPTIONAL: dict[str, type[Lighting | Vibration | TriggerRumble | FanCurve]] = {
    "lighting": Lighting,
    "vibration": Vibration,
    "trigger_rumble": TriggerRumble,
    "fans": FanCurve,
}
"""Settings that stay None until the user sets them, and the parsers of their values."""


def _hold_action(value: object) -> ButtonAction:
    action = ButtonAction(value)
    if action is ButtonAction.L5:
        raise ValueError("Steam gets L5 from the held button by itself")
    return action


def _saturation(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_SATURATION:
        return value
    raise ValueError(f"Saturation must be a percentage from 0 to {MAX_SATURATION}")


def _game_power(value: object) -> tuple[GamePower, ...]:
    if not isinstance(value, list):
        raise ValueError("game_power must be a list")
    profiles = tuple(GamePower.from_json(item) for item in cast("list[object]", value))
    if len(profiles) > MAX_GAME_PROFILES:
        raise ValueError(f"At most {MAX_GAME_PROFILES} games can have their own power")
    if len({profile.app_id for profile in profiles}) != len(profiles):
        raise ValueError("A game can have only one power profile")
    return profiles


def _tab_position(value: object) -> int | None:
    if value is None:
        return None
    # bool is an int in Python; true/false here is a client bug, not a tab key.
    if isinstance(value, int) and not isinstance(value, bool) and value >= FIRST_TAB:
        return value
    raise ValueError(f"Not a quick access tab position: {value!r}")


_FIELDS = frozenset(item.name for item in fields(Settings))


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
