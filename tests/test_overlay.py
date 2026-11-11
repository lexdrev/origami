# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest

from origami import overlay
from origami.blocks import Context
from origami.blocks import overlay as overlay_block
from origami.blocks.overlay import OverlayBlock, offered
from origami.decky_plugins import Conflicts
from origami.journal import ChangeJournal
from origami.overlay import (
    FOCUSABLE_APPS,
    INPUT_FOCUS,
    OVERLAY,
    OverlayKeeper,
    Windows,
    cardinals,
    find_windows,
    menu_runs,
    steams_own,
)
from origami.settings import Settings

from fakes import FakeRoot

MENU = 0x800002
STEAM = 0x2C00035
GAME = 1920490

# The top windows of the user's console in game mode (2026-11-11), with Steam's helpers.
LISTING = """
xwininfo: Window id: 0x407 (the root window) (has no name)

  Root window id: 0x407 (the root window) (has no name)
  Parent window id: 0x0 (none)
     17 children:
     0x2c00035 "Режим Big Picture": ("steamwebhelper" "steam")  1920x1080+0+0  +0+0
     0x2000007 (has no name): ()  1x1+0+0  +0+0
     0x2200003 "steamwebhelper": ("steamwebhelper" "Steamwebhelper")  200x200+0+0  +0+0
     0x180001e "Steam": ("steam" "steam")  48x48+0+0  +0+0
     0x1200041 "VRStream": ("steam" "steam")  32x32+944+524  +944+524
     0x160000e (has no name): ("Steam" "Steam")  64x24+0+0  +0+0
     0x400007 "mangoapp overlay window": ("mangoapp" "mangoapp")  1920x1080+0+0  +0+0
     0x1800001 "steam": ("steam" "Steam")  10x10+10+10  +10+10
     0x800002 "Open Gamepad UI": ("Godot_Engine" "Open Gamepad UI")  1920x1080+320+140  +320+140
"""


def test_the_menu_s_window_and_steam_s_are_found_among_the_display_s() -> None:
    assert find_windows(LISTING) == Windows(menu=MENU, steam=STEAM)
    # Steam's main window is the large one with its class, whichever comes first.
    helper = '     0x1 "steam": ("steamwebhelper" "steam")  1x1+0+0  +0+0\n'
    assert find_windows(helper + LISTING) == Windows(menu=MENU, steam=STEAM)
    assert find_windows(LISTING + helper) == Windows(menu=MENU, steam=STEAM)
    # Without either window there is nothing to keep.
    assert find_windows(LISTING.replace("Open Gamepad UI", "Another")) is None
    assert find_windows(LISTING.replace('"steamwebhelper" "steam"', '"steam" "steam"')) is None
    assert find_windows("") is None


def test_the_properties_are_read_from_xprop_s_lines() -> None:
    output = f"{OVERLAY}(CARDINAL) = 1\n{INPUT_FOCUS}(CARDINAL) = 0\nSTEAM_GAME:  not found.\n"
    assert cardinals(output) == {OVERLAY: (1,), INPUT_FOCUS: (0,)}
    assert cardinals(f"{FOCUSABLE_APPS}(CARDINAL) = 769, 1920490\n") == {
        FOCUSABLE_APPS: (769, GAME)
    }
    assert cardinals(f"{FOCUSABLE_APPS}(CARDINAL) = \n") == {FOCUSABLE_APPS: ()}
    assert cardinals('WM_NAME(STRING) = "Steam"\nnonsense\n') == {}


def test_the_menu_is_known_by_its_process_and_offered_with_the_window_lister(
    fake_root: FakeRoot,
) -> None:
    assert not menu_runs(fake_root.path)
    fake_root.write("proc/3435/comm", "gamescope-wl")
    assert not menu_runs(fake_root.path)
    fake_root.write("proc/3536/comm", "opengamepad-ui.")
    assert menu_runs(fake_root.path)
    assert not offered(fake_root.path)
    fake_root.write("usr/bin/xwininfo", "")
    assert offered(fake_root.path)


def test_steam_means_its_flag_only_with_the_focus_and_a_game_to_show_over() -> None:
    assert steams_own(1, 1, (769, GAME)) == 1
    # Left behind by the menu: over a game without the input focus, or with no game at all.
    assert steams_own(1, 0, (769, GAME)) == 0
    assert steams_own(1, 1, ()) == 0
    assert steams_own(1, 1, (769,)) == 0
    assert steams_own(0, 1, (769,)) == 0


def test_a_flag_the_menu_left_on_steam_s_window_is_taken_off_once_it_closed() -> None:
    # No game runs: the times are those of the console, 22:08:09 on.
    keeper = OverlayKeeper(menu=0, steam=0, own=0)
    assert keeper.wanted(0.0) is None
    keeper.menu_changed(1, 9.209)
    assert keeper.wanted(9.3) is None
    assert keeper.wanted(9.5) is None
    # Closing, the menu sets Steam's flag within the same millisecond.
    keeper.menu_changed(0, 17.517)
    keeper.steam_changed(1, 17.517)
    assert keeper.wanted(17.6) is None
    assert keeper.due(17.6) == pytest.approx(0.117)
    assert keeper.wanted(17.72) == 0
    keeper.written(0, 17.72)
    keeper.steam_changed(0, 17.73)
    assert keeper.wanted(18.0) is None
    assert keeper.due(18.0) is None
    assert keeper.own == 0
    # The next time is the same, in whichever order the two windows report.
    keeper.menu_changed(1, 19.509)
    assert keeper.wanted(19.8) is None
    keeper.steam_changed(1, 22.617)
    keeper.menu_changed(0, 22.618)
    assert keeper.wanted(22.9) == 0


def test_a_flag_left_before_the_fix_went_on_is_taken_off_as_the_menu_opens() -> None:
    keeper = OverlayKeeper(menu=0, steam=1, own=1)
    keeper.menu_changed(1, 5.0)
    # Over a game the menu takes Steam's flag off itself; with no game it does not.
    assert keeper.wanted(5.3) == 0
    keeper.written(0, 5.3)
    keeper.steam_changed(0, 5.31)
    keeper.menu_changed(0, 8.0)
    keeper.steam_changed(1, 8.0)
    # Steam's own flag was 1, so it is as Steam left it.
    assert keeper.wanted(8.3) is None
    assert keeper.own == 1


def test_steam_s_own_flag_for_its_menu_over_a_game_stays() -> None:
    # A game runs: the times are those of the console, 22:13:26 on.
    keeper = OverlayKeeper(menu=0, steam=0, own=0)
    keeper.menu_changed(1, 26.328)
    keeper.menu_changed(0, 30.429)
    keeper.steam_changed(1, 30.430)
    assert keeper.wanted(30.7) == 0
    keeper.written(0, 30.7)
    keeper.steam_changed(0, 30.71)
    # Steam opens its quick access menu: the flag, then the input focus 4 ms later.
    keeper.steam_changed(1, 39.435)
    keeper.steam_focus_changed(39.439)
    assert keeper.wanted(39.7) is None
    assert keeper.own == 1
    # The system's menu over it takes Steam's flag off itself and puts it back.
    keeper.menu_changed(1, 41.0)
    keeper.steam_changed(0, 41.0)
    assert keeper.wanted(41.3) is None
    keeper.menu_changed(0, 43.0)
    keeper.steam_changed(1, 43.0)
    assert keeper.wanted(43.3) is None
    # Steam closes its menu.
    keeper.steam_changed(0, 43.812)
    keeper.steam_focus_changed(43.816)
    assert keeper.wanted(44.1) is None
    assert keeper.own == 0


def test_steam_s_own_flag_right_after_the_menu_closed_is_told_by_its_input_focus() -> None:
    keeper = OverlayKeeper(menu=1, steam=0, own=0)
    keeper.menu_changed(0, 10.0)
    keeper.steam_changed(1, 10.0)
    # The same button opens Steam's menu at once.
    keeper.steam_changed(1, 10.08)
    keeper.steam_focus_changed(10.084)
    assert keeper.wanted(10.2) is None
    assert keeper.wanted(10.3) is None
    assert keeper.own == 1


class FakeDisplay:
    """gamescope's display: two windows with their properties, and the changes xprop reports."""

    def __init__(self) -> None:
        self.listing = LISTING
        self.properties = {MENU: {OVERLAY: 0}, STEAM: {OVERLAY: 0, INPUT_FOCUS: 1}}
        self.focusable = "769"
        self.written: list[tuple[int, str, int]] = []
        self.reports: dict[int, asyncio.Queue[str | None]] = {}
        self.spies = 0

    async def list_windows(self) -> str:
        return self.listing

    async def read(self, window: int | None, *atoms: str) -> str:
        if window is None:
            return f"{FOCUSABLE_APPS}(CARDINAL) = {self.focusable}\n"
        return "".join(self._line(window, atom) for atom in atoms)

    async def write(self, window: int, atom: str, value: int) -> None:
        self.written.append((window, atom, value))
        self.change(window, atom, value)

    async def spy(self, window: int, *atoms: str) -> AsyncGenerator[str]:
        self.spies += 1
        reports = self.reports.setdefault(window, asyncio.Queue())
        for atom in atoms:
            yield self._line(window, atom).rstrip("\n")
        while (line := await reports.get()) is not None:
            yield line

    def change(self, window: int, atom: str, value: int) -> None:
        """Somebody writes a property: the window has it, and xprop reports it."""
        self.properties[window][atom] = value
        if window in self.reports:
            self.reports[window].put_nowait(self._line(window, atom).rstrip("\n"))

    def _line(self, window: int, atom: str) -> str:
        return f"{atom}(CARDINAL) = {self.properties[window][atom]}\n"


async def no_conflicts() -> Conflicts:
    return Conflicts(
        lighting=None,
        saturation=None,
        vibration=None,
        triggers=None,
        power=None,
        boost=None,
        fans=None,
        sound=None,
    )


def make_block(fake_root: FakeRoot, tmp_path: Path, display: FakeDisplay) -> OverlayBlock:
    fake_root.write("proc/3536/comm", "opengamepad-ui.")
    fake_root.write("usr/bin/xwininfo", "")
    journal = ChangeJournal(tmp_path / "changes.json")
    return OverlayBlock(Context(fake_root.path, journal, no_conflicts), display=display)


@pytest.fixture
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    """The keeper settles in hundredths of a second, and the block looks again as often."""
    monkeypatch.setattr(overlay, "SETTLE_SECONDS", 0.04)
    monkeypatch.setattr(overlay, "NEAR_SECONDS", 0.03)
    monkeypatch.setattr(overlay, "OWN_SECONDS", 0.01)
    monkeypatch.setattr(overlay_block, "RETRY_SECONDS", 0.02)
    monkeypatch.setattr(overlay_block, "RECHECK_SECONDS", 0.1)


@pytest.mark.usefixtures("quick")
def test_the_block_puts_steam_s_flag_back_after_the_menu(
    fake_root: FakeRoot, tmp_path: Path
) -> None:
    display = FakeDisplay()
    block = make_block(fake_root, tmp_path, display)

    async def scenario() -> None:
        await block.follow(Settings(overlay_fix=True))
        await asyncio.sleep(0.02)
        assert display.spies == 2
        assert display.written == []
        # The menu opens and closes, leaving its flag on Steam's window.
        display.change(MENU, OVERLAY, 1)
        await asyncio.sleep(0.08)
        assert display.written == []
        display.change(MENU, OVERLAY, 0)
        display.change(STEAM, OVERLAY, 1)
        await asyncio.sleep(0.02)
        assert display.written == []
        await asyncio.sleep(0.08)
        assert display.written == [(STEAM, OVERLAY, 0)]
        # ORIGAMI's own write is not taken for Steam's, and the next time goes the same.
        await asyncio.sleep(0.08)
        display.change(MENU, OVERLAY, 1)
        await asyncio.sleep(0.08)
        display.change(MENU, OVERLAY, 0)
        display.change(STEAM, OVERLAY, 1)
        await asyncio.sleep(0.1)
        assert display.written == [(STEAM, OVERLAY, 0)] * 2
        assert display.properties[STEAM][OVERLAY] == 0
        # Switched off, nothing is watched or written.
        await block.follow(Settings(overlay_fix=False))
        display.change(STEAM, OVERLAY, 1)
        await asyncio.sleep(0.1)
        assert len(display.written) == 2

    asyncio.run(scenario())


@pytest.mark.usefixtures("quick")
def test_the_block_takes_off_a_flag_left_before_it_started(
    fake_root: FakeRoot, tmp_path: Path
) -> None:
    display = FakeDisplay()
    display.properties[STEAM][OVERLAY] = 1
    display.focusable = ""
    block = make_block(fake_root, tmp_path, display)

    async def scenario() -> None:
        await block.follow(Settings(overlay_fix=True))
        await asyncio.sleep(0.05)
        assert display.written == [(STEAM, OVERLAY, 0)]
        block.stop()

    asyncio.run(scenario())


@pytest.mark.usefixtures("quick")
def test_the_block_leaves_steam_s_own_flag_over_a_game(fake_root: FakeRoot, tmp_path: Path) -> None:
    display = FakeDisplay()
    display.properties[STEAM][OVERLAY] = 1
    display.focusable = f"769, {GAME}"
    block = make_block(fake_root, tmp_path, display)

    async def scenario() -> None:
        await block.follow(Settings(overlay_fix=True))
        await asyncio.sleep(0.1)
        assert display.written == []
        block.stop()

    asyncio.run(scenario())


@pytest.mark.usefixtures("quick")
def test_the_block_follows_steam_s_new_window(fake_root: FakeRoot, tmp_path: Path) -> None:
    display = FakeDisplay()
    block = make_block(fake_root, tmp_path, display)
    new = 0x3000001

    async def scenario() -> None:
        await block.follow(Settings(overlay_fix=True))
        await asyncio.sleep(0.02)
        # Steam's interface restarts: its window is a new one.
        display.properties[new] = {OVERLAY: 0, INPUT_FOCUS: 1}
        display.listing = LISTING.replace("0x2c00035", hex(new))
        await asyncio.sleep(0.3)
        assert display.spies == 4
        display.change(MENU, OVERLAY, 1)
        await asyncio.sleep(0.08)
        display.change(MENU, OVERLAY, 0)
        display.change(new, OVERLAY, 1)
        await asyncio.sleep(0.1)
        assert display.written == [(new, OVERLAY, 0)]
        block.stop()

    asyncio.run(scenario())


def test_the_block_does_nothing_without_the_menu_or_the_setting(
    fake_root: FakeRoot, tmp_path: Path
) -> None:
    display = FakeDisplay()
    journal = ChangeJournal(tmp_path / "changes.json")
    block = OverlayBlock(Context(fake_root.path, journal, no_conflicts), display=display)

    async def scenario() -> None:
        # No menu on this system.
        await block.follow(Settings(overlay_fix=True))
        await asyncio.sleep(0.05)
        assert display.spies == 0
        await block.follow(Settings())
        fake_root.write("proc/3536/comm", "opengamepad-ui.")
        fake_root.write("usr/bin/xwininfo", "")
        # Not chosen yet, and switched off.
        await block.follow(Settings())
        await block.follow(Settings(overlay_fix=False))
        await asyncio.sleep(0.05)
        assert display.spies == 0
        block.stop()

    asyncio.run(scenario())


def test_the_setting_is_kept_and_unset_by_restore_everything() -> None:
    settings = Settings().updated({"overlay_fix": True})
    assert settings.overlay_fix is True
    assert settings.to_json()["overlay_fix"] is True
    assert settings.restored().overlay_fix is None
    with pytest.raises(ValueError, match="overlay_fix"):
        Settings().updated({"overlay_fix": "yes"})


@pytest.mark.usefixtures("quick")
def test_the_block_waits_for_a_menu_that_starts_after_the_plugin(
    fake_root: FakeRoot, tmp_path: Path
) -> None:
    display = FakeDisplay()
    journal = ChangeJournal(tmp_path / "changes.json")
    block = OverlayBlock(Context(fake_root.path, journal, no_conflicts), display=display)

    async def scenario() -> None:
        # At boot Decky starts the plugin seconds before the session.
        await block.follow(Settings(overlay_fix=True))
        await asyncio.sleep(0.05)
        assert display.spies == 0
        fake_root.write("usr/bin/xwininfo", "")
        fake_root.write("proc/4464/comm", "opengamepad-ui.")
        await asyncio.sleep(0.08)
        assert display.spies == 2
        block.stop()

    asyncio.run(scenario())
