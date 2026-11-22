# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""What Steam leaves on the disk that can go: shader caches, and the leftovers of removed games.

A game's shader cache is rebuilt as the game runs, so it can go for any game. A game's prefix
(the Windows folders Proton keeps for it) holds its saves and settings: it is offered only for a
game that is not installed any more, as are a shader cache and a game folder left behind.

"Not installed" must be certain. A game counts as installed when any library has its manifest or
Steam's own list of libraries names it, so a library on a card that is not in the slot keeps its
games. While a library or a manifest cannot be read, nothing is taken for a leftover.
"""

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from origami.steamfiles import (
    FIRST_SHORTCUT_ID,
    Library,
    Shortcut,
    parse_shortcuts,
    read_libraries,
    read_manifest,
)

SHADER_CACHES = "shadercache"
PREFIXES = "compatdata"
GAME_FOLDERS = "common"
DOWNLOADS = "downloading"
USER_PART = Path("pfx/drive_c/users/steamuser")
"""The part of a prefix the game writes for the player: saves, settings."""
NAMED_PARTS = ("AppData/Local", "AppData/LocalLow", "AppData/Roaming", "Documents", "Saved Games")
"""Where games make a folder of their own, by whose name a prefix can be recognised."""
EVERY_PREFIX_HAS = frozenset(
    {
        "CrashReportClient",
        "Desktop",
        "Downloads",
        "Microsoft",
        "Music",
        "My Games",
        "Pictures",
        "Temp",
        "Templates",
        "UnrealEngine",
        "Videos",
        "dxvk",
    }
)
MAX_HINTS = 3
STEAM_OWN_FOLDERS = frozenset({"Steam Controller Configs"})
"""Folders among the games' that are Steam's own and have no manifest."""


class Kind(StrEnum):
    SHADERS = "shaders"
    PREFIX = "prefix"
    FOLDER = "folder"


class Owner(StrEnum):
    INSTALLED = "installed"
    REMOVED = "removed"
    """A game of Steam's store that is not installed any more."""
    SHORTCUT = "shortcut"
    """A non-Steam game whose shortcut was removed from Steam."""


@dataclass(frozen=True, slots=True)
class Item:
    """Something the Cleanup screen lists and can remove."""

    key: str
    """What the frontend names the item by; the path stays in the backend."""
    kind: Kind
    owner: Owner
    app_id: int | None
    """None for a game folder: without a manifest nothing tells whose it was."""
    name: str | None
    """The installed game's name, or the folder's; None where only Steam's interface can name
    the game."""
    size: int
    """Bytes on the disk."""
    user_size: int | None = None
    """A prefix: the bytes of the player's own part."""
    hints: tuple[str, ...] = ()
    """A prefix: folders the game made in it, to recognise a game nothing names."""
    busy: bool = False
    """Steam works with the game's files now: not to be removed."""


@dataclass(frozen=True, slots=True)
class Found:
    item: Item
    path: Path


@dataclass(frozen=True, slots=True)
class Survey:
    found: tuple[Found, ...]
    complete: bool
    """Every library and manifest was read: what is not installed is known."""


@dataclass(frozen=True, slots=True)
class _Known:
    """What Steam's files tell of the games it has."""

    installed: frozenset[int]
    names: dict[int, str]
    folders: tuple[frozenset[str], ...]
    """The installed games' folders, library by library."""
    shortcuts: tuple[Shortcut, ...] | None
    """None when a list of shortcuts cannot be read."""
    complete: bool

    def owner(self, app_id: int) -> Owner | None:
        """Whose a cache or a prefix with this id is; None where that cannot be told."""
        if app_id in self.installed:
            return Owner.INSTALLED
        if app_id < FIRST_SHORTCUT_ID:
            return Owner.REMOVED if self.complete else None
        # Without the list of shortcuts a shortcut's files cannot be told from a removed one's.
        return Owner.SHORTCUT if self.shortcuts is not None else None


def survey(steam: Path, *, sizes: bool = True) -> Survey:
    """Look through Steam's libraries; raise OSError or ValueError when their list is unreadable.

    Without `sizes` nothing is measured: enough to check an item again before it is removed.
    """
    libraries = read_libraries(steam)
    known = _read(steam, libraries)
    found: list[Found] = []
    for index, library in enumerate(libraries):
        apps = library.path / "steamapps"
        if apps.is_dir():
            found += _caches(index, apps, known, sizes=sizes)
            found += _game_folders(index, apps, known, sizes=sizes)
    return Survey(tuple(found), known.complete)


def _read(steam: Path, libraries: list[Library]) -> _Known:
    installed: set[int] = set()
    names: dict[int, str] = {}
    folders: list[frozenset[str]] = []
    complete = True
    for library in libraries:
        installed |= library.apps
        own: set[str] = set()
        apps = library.path / "steamapps"
        if not apps.is_dir():
            complete = False
        for path in apps.glob("appmanifest_*.acf"):
            try:
                manifest = read_manifest(path)
            except OSError, ValueError:
                complete = False
                continue
            installed.add(manifest.app_id)
            names[manifest.app_id] = manifest.name
            own.add(manifest.folder)
        folders.append(frozenset(own))
    shortcuts = _shortcuts(steam)
    for shortcut in shortcuts or ():
        installed.add(shortcut.app_id)
        names.setdefault(shortcut.app_id, shortcut.name)
    return _Known(frozenset(installed), names, tuple(folders), shortcuts, complete)


def _caches(index: int, apps: Path, known: _Known, *, sizes: bool) -> list[Found]:
    """The shader caches and the prefixes in a library that can go."""
    found: list[Found] = []
    for kind, folder in ((Kind.SHADERS, SHADER_CACHES), (Kind.PREFIX, PREFIXES)):
        for entry in _folders(apps / folder):
            if not entry.name.isascii() or not entry.name.isdecimal() or int(entry.name) == 0:
                continue
            app_id = int(entry.name)
            owner = known.owner(app_id)
            # An installed game keeps its prefix: its saves are there.
            if owner is None or (owner is Owner.INSTALLED and kind is Kind.PREFIX):
                continue
            path = Path(entry.path)
            prefix = kind is Kind.PREFIX and sizes
            item = Item(
                _key(kind, index, entry.name),
                kind,
                owner,
                app_id,
                known.names.get(app_id) if owner is Owner.INSTALLED else None,
                disk_usage(path) if sizes else 0,
                user_size=disk_usage(path / USER_PART) if prefix else None,
                hints=_hints(path) if prefix else (),
                busy=_downloading(apps / DOWNLOADS / entry.name),
            )
            found.append(Found(item, path))
    return found


def _game_folders(index: int, apps: Path, known: _Known, *, sizes: bool) -> list[Found]:
    """The folders among a library's games that no installed game and no shortcut has."""
    if not known.complete or known.shortcuts is None:
        return []
    found: list[Found] = []
    for entry in _folders(apps / GAME_FOLDERS):
        path = Path(entry.path)
        if entry.name in known.folders[index] or entry.name in STEAM_OWN_FOLDERS:
            continue
        if _used(path, known.shortcuts):
            continue
        size = disk_usage(path) if sizes else 0
        item = Item(
            _key(Kind.FOLDER, index, entry.name), Kind.FOLDER, Owner.REMOVED, None, entry.name, size
        )
        found.append(Found(item, path))
    return found


def _downloading(folder: Path) -> bool:
    """Whether Steam downloads the game now: it keeps the game's folder among the downloads
    afterwards, empty."""
    try:
        with os.scandir(folder) as entries:
            return next(entries, None) is not None
    except OSError:
        return False


def _key(kind: Kind, library: int, name: str) -> str:
    return f"{kind.value}:{library}:{name}"


def _folders(parent: Path) -> list[os.DirEntry[str]]:
    """The plain folders in a folder that is itself no link: what was moved elsewhere and linked
    back is somebody's arrangement, and stays."""
    if parent.is_symlink():
        return []
    try:
        with os.scandir(parent) as entries:
            return sorted(
                (entry for entry in entries if entry.is_dir(follow_symlinks=False)),
                key=lambda entry: entry.name,
            )
    except OSError:
        return []


def _shortcuts(steam: Path) -> tuple[Shortcut, ...] | None:
    """The shortcuts of every Steam user here; None when a list of them cannot be read."""
    shortcuts: list[Shortcut] = []
    for path in sorted((steam / "userdata").glob("*/config/shortcuts.vdf")):
        try:
            shortcuts += parse_shortcuts(path.read_bytes())
        except OSError, ValueError:
            return None
    return tuple(shortcuts)


def _used(folder: Path, shortcuts: tuple[Shortcut, ...]) -> bool:
    """Whether a shortcut runs something in this folder: a game kept there without a manifest."""
    inside = str(folder) + os.sep
    return any(
        path == str(folder) or path.startswith(inside)
        for shortcut in shortcuts
        for path in shortcut.paths
    )


def _hints(prefix: Path) -> tuple[str, ...]:
    hints: list[str] = []
    for part in NAMED_PARTS:
        try:
            names = sorted(entry.name for entry in (prefix / USER_PART / part).iterdir())
        except OSError:
            continue
        hints += [name for name in names if name not in EVERY_PREFIX_HAS and name not in hints]
    return tuple(hints[:MAX_HINTS])


def disk_usage(path: Path) -> int:
    """The bytes a folder takes on the disk, links not followed; 0 where it cannot be read."""
    total = 0
    pending = [str(path)]
    while pending:
        try:
            with os.scandir(pending.pop()) as entries:
                for entry in entries:
                    try:
                        status = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    total += status.st_blocks * 512
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(entry.path)
        except OSError:
            continue
    return total
