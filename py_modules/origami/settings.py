# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
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
from origami.fsutil import atomic_write_text, set_aside
from origami.jsonio import expect_bool, parse_object
from origami.lighting import Lighting
from origami.power import GamePower, Power
from origami.saturation import MAX_PERCENT as MAX_SATURATION
from origami.sound import GameSound, Sound
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
    update_check: bool = False
    """Once a day, as ORIGAMI opens, it asks GitHub for a newer release; off, only on a press."""
    # Fixes of system bugs are None until the user sets them: off all the same, but the screens show
    # them as problems until then. Switched off by hand, they are the user's choice.
    qam_assist: bool | None = None
    """ORIGAMI opens the quick access menu when Steam misses a press of its button (B16)."""
    gyro_fix: bool | None = None
    """ORIGAMI turns the gyroscope's yaw the right way for Steam (B08)."""
    clock_fix: bool | None = None
    """ORIGAMI steps the clock after sleep where the hardware clock keeps local time (B14)."""
    overlay_fix: bool | None = None
    """ORIGAMI keeps the system's overlay menu in sight after its first time (B18)."""
    lighting: Lighting | None = None
    """Lighting of the stick rings; None until the user sets it, so the controller keeps its own."""
    saturation: int | None = None
    """Screen saturation in percent (100 = sRGB); None until the user sets it."""
    vibration: Vibration | None = field(default_factory=Vibration)
    """Handle vibration strength, the middle level from the first start: the controller's own 100%
    is too strong. None, after "restore everything", leaves the controller's own until it is set."""
    trigger_rumble: TriggerRumble | None = None
    """Rumble of the impulse triggers (B19); None until the user chooses, and they stay still."""
    armoury_crate: ButtonAction | None = None
    """What a short press of the upper left button does; nothing reaches Steam from it (B17).
    None until the user sets it, and nothing then too."""
    armoury_crate_hold: ButtonAction | None = None
    """What holding the upper left button does, besides the L5 Steam gets from it."""
    manage_tdp: bool | None = True
    """ORIGAMI owns the TDP and writes it again whenever it drops (B04, B05); off, Steam sets it.
    None after "restore everything" until the user decides: off all the same, but a problem, as
    an unset fix is."""
    power: Power = field(default_factory=Power)
    """TDP, its headroom and the CPU boost; the factory's limits until the user changes them."""
    battery_high_tdp: bool = False
    """The TDP may go over 25 W on the battery too."""
    game_power: tuple[GamePower, ...] = ()
    """Games with power settings of their own, one profile each."""
    fans: FanCurve | None = None
    """ORIGAMI's curve for both fans (B07); None until switched on: the firmware's own."""
    sound: Sound | None = None
    """ORIGAMI's filter in front of the speakers; None until switched on: the system's sound."""
    game_sound: tuple[GameSound, ...] = ()
    """Games with a sound of their own, one profile each."""

    def power_for(self, game: int | None) -> Power:
        """The power a game runs with: its own profile while that is active, else the general."""
        for profile in self.game_power:
            if profile.app_id == game and profile.active:
                return profile.power
        return self.power

    def sound_for(self, game: int | None) -> Sound | None:
        """The sound a game runs with: its own profile while that is active, else the general."""
        for profile in self.game_sound:
            if profile.app_id == game and profile.active:
                return profile.sound
        return self.sound

    def restored(self) -> Settings:
        """These settings after "restore everything": nothing of the system is left to ORIGAMI.

        The fixes and all ORIGAMI drives are unset again, so the screens show the bugs as problems,
        and Steam sets the TDP, which is a problem too until the user decides. The interface and the
        daily update check stay, and so do the TDP and the games' profiles for the next time ORIGAMI
        manages it, without their CPU boost: that flag is the system's again. The games' sounds
        stay too, but waiting: none of them runs until its game's switch goes on again.
        """
        return Settings(
            language=self.language,
            qam_tab=self.qam_tab,
            qam_tab_before=self.qam_tab_before,
            update_check=self.update_check,
            vibration=None,
            manage_tdp=None,
            power=replace(self.power, cpu_boost=None),
            battery_high_tdp=self.battery_high_tdp,
            game_power=tuple(
                replace(profile, power=replace(profile.power, cpu_boost=None))
                for profile in self.game_power
            ),
            game_sound=tuple(replace(profile, active=False) for profile in self.game_sound),
        )

    def updated(self, changes: Mapping[str, object]) -> Settings:
        """Return a copy with the given fields changed; raise ValueError on bad input."""
        parsed: dict[str, object] = {}
        for key, value in changes.items():
            match key:
                case "language":
                    parsed[key] = Language(value)
                case "qam_tab" | "battery_high_tdp" | "update_check":
                    parsed[key] = expect_bool(key, value)
                case "qam_assist" | "gyro_fix" | "clock_fix" | "overlay_fix" | "manage_tdp":
                    parsed[key] = None if value is None else expect_bool(key, value)
                case "qam_tab_before":
                    parsed[key] = _tab_position(value)
                case "lighting" | "vibration" | "trigger_rumble" | "fans" | "sound":
                    parsed[key] = None if value is None else _OPTIONAL[key].from_json(value)
                case "saturation":
                    parsed[key] = _saturation(value)
                case "armoury_crate":
                    parsed[key] = None if value is None else ButtonAction(value)
                case "armoury_crate_hold":
                    parsed[key] = None if value is None else _hold_action(value)
                case "power":
                    parsed[key] = Power.from_json(value)
                case "game_power" | "game_sound":
                    parsed[key] = _game_profiles(key, value)
                case _:
                    raise ValueError(f"Unknown setting: {key}")
        return replace(self, **parsed)

    def to_json(self) -> dict[str, object]:
        return {
            "version": SCHEMA_VERSION,
            "language": self.language.value,
            "qam_tab": self.qam_tab,
            "qam_tab_before": self.qam_tab_before,
            "update_check": self.update_check,
            "qam_assist": self.qam_assist,
            "gyro_fix": self.gyro_fix,
            "clock_fix": self.clock_fix,
            "overlay_fix": self.overlay_fix,
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
            "sound": None if self.sound is None else self.sound.to_json(),
            "game_sound": [profile.to_json() for profile in self.game_sound],
        }


_OPTIONAL: dict[str, type[Lighting | Vibration | TriggerRumble | FanCurve | Sound]] = {
    "lighting": Lighting,
    "vibration": Vibration,
    "trigger_rumble": TriggerRumble,
    "fans": FanCurve,
    "sound": Sound,
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


_GAME_PROFILES: dict[str, type[GamePower | GameSound]] = {
    "game_power": GamePower,
    "game_sound": GameSound,
}
"""The games' own settings, and the parsers of their profiles."""


def _game_profiles(key: str, value: object) -> tuple[GamePower | GameSound, ...]:
    """The games' own power or sound: a list with one profile a game."""
    kind, what = _GAME_PROFILES[key], key.removeprefix("game_")
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    profiles = tuple(kind.from_json(item) for item in cast("list[object]", value))
    if len(profiles) > MAX_GAME_PROFILES:
        raise ValueError(f"At most {MAX_GAME_PROFILES} games can have their own {what}")
    if len({profile.app_id for profile in profiles}) != len(profiles):
        raise ValueError(f"A game can have only one {what} profile")
    return profiles


def _tab_position(value: object) -> int | None:
    if value is None:
        return None
    # bool is an int in Python; true/false here is a client bug, not a tab key.
    if isinstance(value, int) and not isinstance(value, bool) and value >= FIRST_TAB:
        return value
    raise ValueError(f"Not a quick access tab position: {value!r}")


_FIELDS = frozenset(item.name for item in fields(Settings))


def describe_changes(before: Settings, after: Settings) -> str:
    """The settings that differ, with their new values, for one line of the log.

    A game's profile is told by itself, not the whole list of them.
    """
    old, new = before.to_json(), after.to_json()
    told = [
        f"{key} {_compact(value)}"
        for key, value in new.items()
        if key not in ("game_power", "game_sound") and value != old.get(key)
    ]
    told += _game_changes("game", before.game_power, after.game_power)
    told += _game_changes("game sound", before.game_sound, after.game_sound)
    return "; ".join(told)


def _game_changes(
    what: str,
    before: tuple[GamePower, ...] | tuple[GameSound, ...],
    after: tuple[GamePower, ...] | tuple[GameSound, ...],
) -> list[str]:
    was = {profile.app_id: profile for profile in before}
    now = {profile.app_id for profile in after}
    told = [
        f"{what} {profile.app_id} {_compact(profile.to_json())}"
        for profile in after
        if was.get(profile.app_id) != profile
    ]
    return told + [f"{what} {app_id} removed" for app_id in was if app_id not in now]


def _compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


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
        except ValueError as error:
            _set_aside(self._path, "settings", error)
            return Settings()
        # Keys written by a newer version are skipped, so a downgrade keeps working, and a value
        # this version cannot read costs only its own setting.
        settings = Settings()
        for key in sorted(data.keys() & _FIELDS):
            try:
                settings = settings.updated({key: data[key]})
            except ValueError as error:
                log.warning("Ignoring the setting %s in %s: %s", key, self._path, error)
        return settings

    def save(self, settings: Settings) -> None:
        atomic_write_text(self._path, json.dumps(settings.to_json(), indent=2) + "\n")


def _set_aside(path: Path, what: str, error: ValueError) -> None:
    try:
        aside = set_aside(path)
    except OSError as move_error:
        log.error("Unreadable %s in %s, not moved aside: %s; %s", what, path, error, move_error)
        return
    log.error(
        "Unreadable %s in %s, kept as %s; starting from defaults: %s", what, path, aside, error
    )
