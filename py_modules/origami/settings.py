# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass, fields
from enum import StrEnum
from pathlib import Path

from origami.fsutil import atomic_write_text
from origami.jsonio import parse_object

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1


class Language(StrEnum):
    AUTO = "auto"
    RU = "ru"
    EN = "en"


@dataclass(frozen=True, slots=True)
class Settings:
    language: Language = Language.AUTO

    def updated(self, changes: Mapping[str, object]) -> Settings:
        """Return a copy with the given fields changed; raise ValueError on bad input."""
        language = self.language
        for key, value in changes.items():
            match key:
                case "language":
                    language = Language(value)
                case _:
                    raise ValueError(f"Unknown setting: {key}")
        return Settings(language=language)

    def to_json(self) -> dict[str, object]:
        return {"version": SCHEMA_VERSION, "language": self.language.value}


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
