# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from pathlib import Path

import pytest

from origami.blocks.cleanup import CleanupBlock, CleanupScan, Storage
from origami.cleanup import Item, Kind, Owner, disk_usage

from fakes import FakeSteam, FakeUser, shortcuts_vdf

INSTALLED = 597820
REMOVED = 617290
SHORTCUT = 3293947715
"""A non-Steam game's id: Steam gives those from 2^31 up."""


def make_block(tmp_path: Path, user: FakeUser | None = None) -> tuple[CleanupBlock, FakeSteam]:
    """A block over a home with Steam, an installed game and no shortcuts."""
    home = tmp_path / "root" / "home" / "user"
    steam = FakeSteam(home)
    steam.install(INSTALLED, "Installed Game")
    steam.shortcuts(shortcuts_vdf())
    return CleanupBlock(
        tmp_path / "root", home=home, runner=user or FakeUser(), disk=same_disk
    ), steam


def same_disk(_home: Path) -> Storage:
    """A disk whose free space does not tell what a removal gained."""
    return Storage(free=50 * 2**30, total=100 * 2**30)


def scan(block: CleanupBlock) -> CleanupScan:
    return asyncio.run(block.scan())


def listed(found: CleanupScan) -> set[tuple[Kind, Owner, int | None, str | None]]:
    return {(item.kind, item.owner, item.app_id, item.name) for item in found.items}


def item(found: CleanupScan, kind: Kind, app_id: int) -> Item:
    return next(item for item in found.items if item.kind is kind and item.app_id == app_id)


def process(
    tmp_path: Path, pid: int, *, environ: str = "", comm: str = "game", cmdline: str = ""
) -> None:
    """A process as /proc shows it."""
    folder = tmp_path / "root" / "proc" / str(pid)
    folder.mkdir(parents=True)
    (folder / "environ").write_bytes(environ.encode() + b"\0")
    (folder / "comm").write_text(comm + "\n", encoding="utf-8")
    (folder / "cmdline").write_bytes(cmdline.replace(" ", "\0").encode() + b"\0")


def test_a_home_without_steam_has_nothing_to_clean(tmp_path: Path) -> None:
    home = tmp_path / "root" / "home" / "user"
    home.mkdir(parents=True)
    block = CleanupBlock(tmp_path / "root", home=home, runner=FakeUser())

    assert not block.supported()
    with pytest.raises(ValueError):
        scan(block)

    FakeSteam(home)
    assert block.supported()


def test_an_installed_game_offers_its_shader_cache_and_keeps_its_prefix(tmp_path: Path) -> None:
    block, steam = make_block(tmp_path)
    steam.shaders(INSTALLED)
    steam.prefix(INSTALLED)

    found = scan(block)

    assert listed(found) == {(Kind.SHADERS, Owner.INSTALLED, INSTALLED, "Installed Game")}
    assert found.complete and not found.game
    assert found.items[0].size > 0
    assert found.storage.total >= found.storage.free > 0


def test_a_removed_game_offers_all_it_left(tmp_path: Path) -> None:
    block, steam = make_block(tmp_path)
    steam.shaders(REMOVED)
    prefix = steam.prefix(REMOVED, saves="Remnant")
    steam.game_folder("Remnant")

    found = scan(block)

    # Only Steam's interface can name a game that has no manifest; its folder has a name.
    assert listed(found) == {
        (Kind.SHADERS, Owner.REMOVED, REMOVED, None),
        (Kind.PREFIX, Owner.REMOVED, REMOVED, None),
        (Kind.FOLDER, Owner.REMOVED, None, "Remnant"),
    }
    left = item(found, Kind.PREFIX, REMOVED)
    assert left.size == disk_usage(prefix)
    # The player's own part of the prefix, and the folder the game made in it.
    assert 0 < (left.user_size or 0) < left.size
    assert left.hints == ("Remnant",)
    assert [entry.size for entry in found.items] == sorted(
        (entry.size for entry in found.items), reverse=True
    )


def test_what_is_not_a_game_s_plain_folder_is_not_listed(tmp_path: Path) -> None:
    block, steam = make_block(tmp_path)
    apps = steam.folder / "steamapps"
    steam.prefix(0)
    steam.shaders("notes")
    steam.game_folder("Steam Controller Configs")
    moved = steam.shaders(REMOVED, library=tmp_path / "elsewhere")
    (apps / "shadercache" / str(REMOVED)).symlink_to(moved)
    (apps / "common" / "Steam.dll").symlink_to(tmp_path / "elsewhere")
    (apps / "compatdata" / "617291").write_text("a file", encoding="utf-8")

    assert listed(scan(block)) == set()


def test_caches_moved_elsewhere_as_a_whole_stay(tmp_path: Path) -> None:
    block, steam = make_block(tmp_path)
    moved = steam.shaders(REMOVED, library=tmp_path / "card").parent
    (steam.folder / "steamapps" / "shadercache").symlink_to(moved)

    assert listed(scan(block)) == set()


def test_a_shortcut_s_files_are_leftovers_only_once_it_is_removed(tmp_path: Path) -> None:
    block, steam = make_block(tmp_path)
    steam.shaders(SHORTCUT)
    steam.prefix(SHORTCUT)
    steam.shortcuts(shortcuts_vdf((SHORTCUT, "Other Game", "/games/other/run.exe")))

    assert listed(scan(block)) == {(Kind.SHADERS, Owner.INSTALLED, SHORTCUT, "Other Game")}

    steam.shortcuts(shortcuts_vdf())
    assert listed(scan(block)) == {
        (Kind.SHADERS, Owner.SHORTCUT, SHORTCUT, None),
        (Kind.PREFIX, Owner.SHORTCUT, SHORTCUT, None),
    }


def test_without_the_list_of_shortcuts_none_counts_as_removed(tmp_path: Path) -> None:
    block, steam = make_block(tmp_path)
    steam.shaders(SHORTCUT)
    steam.prefix(SHORTCUT)
    steam.shaders(REMOVED)
    steam.game_folder("Left Behind")
    steam.shortcuts(b"not the list")

    # A game folder may be a shortcut's too: it stays as well.
    assert listed(scan(block)) == {(Kind.SHADERS, Owner.REMOVED, REMOVED, None)}


def test_a_folder_a_shortcut_runs_from_is_not_a_leftover(tmp_path: Path) -> None:
    block, steam = make_block(tmp_path)
    kept = steam.game_folder("Kept Game")
    steam.game_folder("Kept Game 2")
    steam.shortcuts(shortcuts_vdf((SHORTCUT, "Kept", f"{kept}/bin/run.exe")))

    assert listed(scan(block)) == {(Kind.FOLDER, Owner.REMOVED, None, "Kept Game 2")}


def test_a_library_that_is_not_mounted_keeps_its_games(tmp_path: Path) -> None:
    block, steam = make_block(tmp_path)
    card = steam.library(tmp_path / "card", mounted=False)
    steam.install(REMOVED, "On the card", card)
    steam.shaders(REMOVED)
    steam.prefix(REMOVED)
    steam.shaders(INSTALLED)
    steam.shaders(700)
    steam.game_folder("Left Behind")

    found = scan(block)

    # The card's game is installed; what else is not installed cannot be told without the card.
    assert not found.complete
    assert listed(found) == {
        (Kind.SHADERS, Owner.INSTALLED, REMOVED, None),
        (Kind.SHADERS, Owner.INSTALLED, INSTALLED, "Installed Game"),
    }


def test_a_manifest_that_cannot_be_read_leaves_nothing_for_a_leftover(tmp_path: Path) -> None:
    block, steam = make_block(tmp_path)
    steam.shaders(REMOVED)
    steam.game_folder("Left Behind")
    (steam.folder / "steamapps" / "appmanifest_700.acf").write_text(
        '"AppState" {', encoding="utf-8"
    )

    found = scan(block)

    assert not found.complete
    assert listed(found) == set()


def test_while_a_game_runs_nothing_is_listed_or_removed(tmp_path: Path) -> None:
    user = FakeUser()
    block, steam = make_block(tmp_path, user)
    cache = steam.shaders(REMOVED)
    key = scan(block).items[0].key
    process(tmp_path, 300, environ=f"HOME=/home/user\0SteamAppId={INSTALLED}")

    found = scan(block)
    assert found.game and found.items == ()
    assert found.storage.total > 0

    cleaned = asyncio.run(block.clean([key]))
    assert cleaned.freed == 0 and cleaned.failed == (key,)
    assert cache.exists() and user.calls == []


def test_a_game_whose_shaders_steam_compiles_now_is_busy(tmp_path: Path) -> None:
    user = FakeUser()
    block, steam = make_block(tmp_path, user)
    steam.shaders(INSTALLED)
    steam.shaders(REMOVED)
    process(
        tmp_path,
        400,
        comm="fossilize_repla",
        cmdline=f"fossilize_replay {steam.shaders(INSTALLED)}/fozpipelinesv6/a.foz",
    )

    found = scan(block)
    assert item(found, Kind.SHADERS, INSTALLED).busy
    assert not item(found, Kind.SHADERS, REMOVED).busy

    busy = item(found, Kind.SHADERS, INSTALLED).key
    assert asyncio.run(block.clean([busy])).failed == (busy,)
    assert user.calls == []

    # Work whose game cannot be told keeps every cache.
    process(tmp_path, 401, comm="fossilize_repla", cmdline="fossilize_replay --quiet")
    assert all(entry.busy for entry in scan(block).items)


def test_a_game_steam_downloads_now_is_busy(tmp_path: Path) -> None:
    block, steam = make_block(tmp_path)
    steam.shaders(INSTALLED)
    download = steam.folder / "steamapps" / "downloading" / str(INSTALLED)
    download.mkdir(parents=True)

    # Steam leaves the folder behind, empty, once the download is done.
    assert not item(scan(block), Kind.SHADERS, INSTALLED).busy

    (download / "depot.chunk").write_bytes(b"d")
    assert item(scan(block), Kind.SHADERS, INSTALLED).busy


def test_the_picked_items_are_removed_as_the_user(tmp_path: Path) -> None:
    user = FakeUser()
    block, steam = make_block(tmp_path, user)
    cache = steam.shaders(INSTALLED)
    prefix = steam.prefix(REMOVED)
    folder = steam.game_folder("Left Behind")
    found = scan(block)
    picked = [item(found, Kind.SHADERS, INSTALLED), item(found, Kind.PREFIX, REMOVED)]

    cleaned = asyncio.run(
        block.clean([entry.key for entry in picked] + ["shaders:0:999", "nonsense"])
    )

    assert cleaned.freed == sum(entry.size for entry in picked)
    assert cleaned.failed == ("shaders:0:999", "nonsense")
    assert not cache.exists() and not prefix.exists()
    assert folder.exists()
    home = tmp_path / "root" / "home" / "user"
    assert set(user.users) == {(home.stat().st_uid, home.stat().st_gid)}
    assert [call[:4] for call in user.calls] == [
        ("rm", "-rf", "--one-file-system", "--"),
        ("rm", "-rf", "--one-file-system", "--"),
        ("sync", "-f", str(steam.folder / "steamapps")),
    ]
    # Removed once, an item is not on the list any more.
    assert asyncio.run(block.clean([picked[0].key])).failed == (picked[0].key,)


def test_a_game_installed_since_the_scan_keeps_its_files(tmp_path: Path) -> None:
    user = FakeUser()
    block, steam = make_block(tmp_path, user)
    prefix = steam.prefix(REMOVED)
    folder = steam.game_folder("Back Again")
    found = scan(block)
    keys = [entry.key for entry in found.items]
    steam.install(REMOVED, "Back Again")

    cleaned = asyncio.run(block.clean(keys))

    assert cleaned.freed == 0 and set(cleaned.failed) == set(keys)
    assert prefix.exists() and folder.exists()
    assert user.calls == []


def test_what_cannot_be_removed_is_told_back(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    user = FakeUser()
    block, steam = make_block(tmp_path, user)
    cache = steam.shaders(REMOVED)
    key = scan(block).items[0].key
    user.failing = "rm"

    cleaned = asyncio.run(block.clean([key]))

    assert cleaned.freed == 0 and cleaned.failed == (key,)
    assert cache.exists()
    assert "Not cleaned up" in caplog.text
    # It stays on the list, for the next try.
    user.failing = None
    assert asyncio.run(block.clean([key])).failed == ()


class Disk:
    """A disk whose free space grows by `gain` each time a removal is written out."""

    def __init__(self, user: FakeUser) -> None:
        self.free = 10 * 2**30
        self.gain = 0
        self._user = user

    def storage(self, _home: Path) -> Storage:
        return Storage(self.free, 100 * 2**30)

    def run(self, *args: str, timeout: float, user: tuple[int, int] | None = None) -> str:
        if args[0] == "sync":
            self.free += self.gain
        return self._user(*args, timeout=timeout, user=user)


def test_the_cleanup_tells_what_the_disk_gained(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    user = FakeUser()
    disk = Disk(user)
    home = tmp_path / "root" / "home" / "user"
    steam = FakeSteam(home)
    steam.shortcuts(shortcuts_vdf())
    block = CleanupBlock(tmp_path / "root", home=home, runner=disk.run, disk=disk.storage)

    def clean(gain: int) -> tuple[int, int]:
        """Remove a shader cache; returns what the cleanup tells and what the cache took."""
        steam.shaders(REMOVED)
        found = scan(block).items[0]
        disk.gain = gain
        return asyncio.run(block.clean([found.key])).freed, found.size

    # Blocks shared with other files stay: the disk gains less than the cache took.
    freed, size = clean(4096)
    assert freed == 4096 < size
    # What something else freed meanwhile is not the cleanup's.
    freed, size = clean(10 * 2**20)
    assert freed == size
    # A disk that tells nothing, and a removal that could not be written out: what the cache took.
    freed, size = clean(0)
    assert freed == size
    user.failing = "sync"
    freed, size = clean(4096)
    assert freed == size
    assert "The free space is not up to date yet" in caplog.text
