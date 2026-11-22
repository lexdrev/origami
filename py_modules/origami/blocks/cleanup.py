# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Service tile's cleanup: Steam's shader caches and the leftovers of removed games."""

import asyncio
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from origami.cleanup import Found, Item, Kind, survey
from origami.gameprocs import game_runs, shader_work
from origami.proc import CommandError, run_blocking
from origami.steamfiles import steam_folder

log = logging.getLogger(__name__)

REMOVE_SECONDS = 300.0
"""A game folder left behind may hold gigabytes; a cache or a prefix goes in a second."""
SYNC_SECONDS = 20.0
"""The file system writes the removal out: a moment, more while a game is being installed."""


class Runner(Protocol):
    """origami.proc.run_blocking, as the block calls it."""

    def __call__(self, *args: str, timeout: float, user: tuple[int, int] | None = None) -> str: ...


@dataclass(frozen=True, slots=True)
class Storage:
    """The disk the user's home is on."""

    free: int
    total: int


def read_storage(home: Path) -> Storage:
    """Raise OSError when the home is not there."""
    disk = os.statvfs(home)
    return Storage(disk.f_bavail * disk.f_frsize, disk.f_blocks * disk.f_frsize)


@dataclass(frozen=True, slots=True)
class CleanupScan:
    """What the Cleanup screen shows."""

    items: tuple[Item, ...]
    storage: Storage
    complete: bool
    """Every Steam library was read; else the leftovers of removed games are not told."""
    game: bool
    """A game runs: nothing is listed, and nothing can be removed."""


@dataclass(frozen=True, slots=True)
class Cleaned:
    freed: int
    """Bytes the disk gained. Files may share their blocks with others (btrfs), so this can be
    less than the removed items took; where the gain cannot be told, it is what they took."""
    failed: tuple[str, ...]
    """The keys of the items that stay."""


class CleanupBlock:
    """Lists what can go from Steam's folders and removes what the user picks.

    Only what the last scan listed can be removed, and each item is looked at again right before:
    a game installed, launched or downloaded meanwhile keeps its files. ORIGAMI runs as root, so
    the removing is done by a program run as the user: it can remove only what the user can,
    whatever links the folders hold.
    """

    def __init__(
        self,
        root: Path,
        *,
        home: Path,
        runner: Runner | None = None,
        disk: Callable[[Path], Storage] = read_storage,
    ) -> None:
        self._root = root
        self._home = home
        self._run: Runner = run_blocking if runner is None else runner
        self._disk = disk
        self._listed: dict[str, Found] = {}
        self._lock = asyncio.Lock()

    def supported(self) -> bool:
        """Steam keeps its games in this home."""
        return steam_folder(self._home) is not None

    def storage(self) -> Storage:
        """Raise OSError when the home is not there."""
        return self._disk(self._home)

    async def scan(self) -> CleanupScan:
        """Raise OSError or ValueError when Steam's list of libraries cannot be read."""
        async with self._lock:
            return await asyncio.to_thread(self._scan)

    async def clean(self, keys: list[str]) -> Cleaned:
        """Remove the listed items with these keys; what cannot go is told back."""
        async with self._lock:
            return await asyncio.to_thread(self._clean, keys)

    def _scan(self) -> CleanupScan:
        steam = steam_folder(self._home)
        if steam is None:
            raise ValueError("Steam's folder is not in the user's home")
        if game_runs(self._root):
            # Steam and the game write into these folders now, and measuring them loads the disk.
            self._listed = {}
            return CleanupScan((), self.storage(), complete=True, game=True)
        found = survey(steam)
        busy, every = shader_work(self._root)
        listed = [
            replace(entry, item=replace(entry.item, busy=True))
            if _in_work(entry.item, busy, every=every)
            else entry
            for entry in found.found
        ]
        self._listed = {entry.item.key: entry for entry in listed}
        items = sorted((entry.item for entry in listed), key=lambda item: -item.size)
        return CleanupScan(tuple(items), self.storage(), complete=found.complete, game=False)

    def _clean(self, keys: list[str]) -> Cleaned:
        steam = steam_folder(self._home)
        wanted = [self._listed[key] for key in dict.fromkeys(keys) if key in self._listed]
        unknown = [key for key in dict.fromkeys(keys) if key not in self._listed]
        if steam is None or game_runs(self._root):
            return Cleaned(0, tuple(keys))
        try:
            now = {entry.item.key: entry for entry in survey(steam, sizes=False).found}
        except (OSError, ValueError) as error:
            log.warning("Nothing cleaned up: %s", error)
            return Cleaned(0, tuple(keys))
        busy, every = shader_work(self._root)
        owner = self._home.stat()
        user = owner.st_uid, owner.st_gid
        free = self.storage().free
        removed = 0
        failed = unknown
        for entry in wanted:
            item, path = entry.item, entry.path
            again = now.get(item.key)
            # Still the same thing: not installed since, not downloaded now, not being compiled.
            same = (
                again is not None
                and again.path == path
                and again.item.owner is item.owner
                and not again.item.busy
                and not _in_work(item, busy, every=every)
            )
            if same and self._remove(path, user):
                removed += item.size
                del self._listed[item.key]
                log.info("Cleaned up %s (%d MiB)", item.key, item.size // 2**20)
            else:
                failed.append(item.key)
        gained = self._gained(steam, user, free) if removed else 0
        return Cleaned(min(gained, removed) if gained > 0 else removed, tuple(failed))

    def _gained(self, steam: Path, user: tuple[int, int], free: int) -> int:
        """The bytes the disk has more than before, once the removal is written out.

        A file system that frees blocks as it commits (btrfs: within half a minute) shows the old
        free space until then, so the commit is asked for now.
        """
        try:
            self._run("sync", "-f", str(steam / "steamapps"), timeout=SYNC_SECONDS, user=user)
        except (CommandError, TimeoutError) as error:
            log.warning("The free space is not up to date yet: %s", error)
            return 0
        return self.storage().free - free

    def _remove(self, path: Path, user: tuple[int, int]) -> bool:
        try:
            self._run(
                "rm", "-rf", "--one-file-system", "--", str(path), timeout=REMOVE_SECONDS, user=user
            )
        except (CommandError, TimeoutError) as error:
            log.warning("Not cleaned up: %s", error)
        return not os.path.lexists(path)


def _in_work(item: Item, busy: frozenset[int], *, every: bool) -> bool:
    """Whether Steam compiles this game's shaders now, into the cache or with its prefix."""
    if item.kind is Kind.FOLDER:
        return False
    return every or item.app_id in busy
