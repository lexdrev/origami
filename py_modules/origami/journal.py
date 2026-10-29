# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""What ORIGAMI changed in the system and the values it has to restore.

The journal lives on disk so that originals survive a crash or a reboot, and
"restore everything" works even if the plugin was not stopped cleanly.
"""

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path

from origami.fsutil import atomic_write_text
from origami.jsonio import JsonValue, parse_object

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class Change:
    module: str
    key: str
    original: JsonValue


class ChangeJournal:
    """The changes, kept on disk; safe to use from the worker threads that change the hardware."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._changes: dict[tuple[str, str], Change] = {}
        self._lock = threading.Lock()

    def load(self) -> None:
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self._changes = {}
            return
        try:
            changes = _parse(text)
        except ValueError as error:
            # Losing originals is serious, but refusing to start would be worse:
            # modules still know the firmware defaults and can fall back to them.
            log.error("Change journal %s is unreadable, starting empty: %s", self._path, error)
            changes = []
        with self._lock:
            self._changes = {(change.module, change.key): change for change in changes}

    def entries(self) -> list[Change]:
        with self._lock:
            return list(self._changes.values())

    def recorded(self, module: str, key: str) -> bool:
        with self._lock:
            return (module, key) in self._changes

    def original(self, module: str, key: str) -> JsonValue:
        """The value from before ORIGAMI's first change; None also when nothing is recorded."""
        with self._lock:
            change = self._changes.get((module, key))
        return None if change is None else change.original

    def record(self, module: str, key: str, original: JsonValue) -> None:
        """Remember the value before the first change; later changes keep that original."""
        with self._lock:
            if (module, key) in self._changes:
                return
            self._changes[module, key] = Change(module, key, original)
            self._save()

    def forget(self, module: str, key: str) -> None:
        with self._lock:
            if self._changes.pop((module, key), None) is not None:
                self._save()

    def _save(self) -> None:
        """Write the journal out; the caller holds the lock, so no other change slips in."""
        if not self._changes:
            self._path.unlink(missing_ok=True)
            return
        document = {
            "version": SCHEMA_VERSION,
            "changes": [
                {"module": change.module, "key": change.key, "original": change.original}
                for change in self._changes.values()
            ],
        }
        atomic_write_text(self._path, json.dumps(document, indent=2) + "\n")


def _parse(text: str) -> list[Change]:
    items = parse_object(text).get("changes")
    if not isinstance(items, list):
        raise ValueError("'changes' must be a list")
    return [_parse_change(item) for item in items]


def _parse_change(item: JsonValue) -> Change:
    if not isinstance(item, dict):
        raise ValueError("journal entry must be an object")
    module, key = item.get("module"), item.get("key")
    if not isinstance(module, str) or not isinstance(key, str):
        raise ValueError("journal entry needs 'module' and 'key' strings")
    return Change(module, key, item.get("original"))
