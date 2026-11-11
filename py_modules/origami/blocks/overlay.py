# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Keeps the system's overlay menu in sight (B18): see origami.overlay for what goes wrong.

While the fix is on, the block watches the overlay flags of the menu's window and of Steam's and
writes Steam's back as Steam itself last set it. It changes nothing that lasts: the flag is Steam's
own again with its next menu, and a new Steam window starts without it.
"""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import aclosing, suppress
from pathlib import Path
from typing import Protocol

from origami import gamescope
from origami.blocks import Context
from origami.overlay import (
    FOCUSABLE_APPS,
    INPUT_FOCUS,
    LISTER,
    OVERLAY,
    OverlayKeeper,
    Windows,
    cardinals,
    find_windows,
    menu_runs,
    steams_own,
)
from origami.proc import CommandError
from origami.settings import Settings
from origami.tasks import BackgroundTask

log = logging.getLogger(__name__)

RETRY_SECONDS = 5.0
"""How long until the windows are looked for again: the menu or Steam may not be up yet."""
RECHECK_SECONDS = 10.0
"""How often a watch looks whether its windows are still the ones: Steam's is new after its
interface restarts."""


class Display(Protocol):
    """gamescope's display as the block uses it; the tests have their own."""

    async def list_windows(self) -> str: ...

    async def read(self, window: int | None, *atoms: str) -> str:
        """xprop's lines for a window's properties, the root window's for None."""
        ...

    async def write(self, window: int, atom: str, value: int) -> None: ...

    def spy(self, window: int, *atoms: str) -> AsyncGenerator[str]: ...


class GamescopeDisplay:
    def __init__(self, root: Path) -> None:
        self._root = root

    async def list_windows(self) -> str:
        return await gamescope.list_windows(self._root)

    async def read(self, window: int | None, *atoms: str) -> str:
        if window is None:
            return await gamescope.read_root(self._root, *atoms)
        return await gamescope.read_window(self._root, window, *atoms)

    async def write(self, window: int, atom: str, value: int) -> None:
        await gamescope.write_window_cardinal(self._root, window, atom, value)

    def spy(self, window: int, *atoms: str) -> AsyncGenerator[str]:
        return gamescope.spy_window(self._root, window, *atoms)


def offered(root: Path) -> bool:
    """Whether the fix has a menu to keep and the program that finds its window."""
    return (root / LISTER).exists() and menu_runs(root)


class OverlayBlock:
    def __init__(
        self,
        context: Context,
        *,
        display: Display | None = None,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._root = context.root
        self._display = display if display is not None else GamescopeDisplay(context.root)
        self._now = now
        self._keeper = BackgroundTask("origami-overlay", self._keep)
        self._problem: str | None = None
        self._told = False

    async def follow(self, settings: Settings) -> None:
        # At boot the plugin starts before the session and its menu: the keeper waits for it.
        await self._keeper.run_while(on=settings.overlay_fix is True)

    def stop(self) -> None:
        self._keeper.cancel()

    async def _keep(self) -> None:
        while True:
            try:
                # No menu here, or none yet, is no problem to tell of.
                if await asyncio.to_thread(offered, self._root):
                    windows = find_windows(await self._display.list_windows())
                    if windows is None:
                        # So it is while the session starts and while Steam restarts.
                        self._wait()
                    else:
                        self._problem = None
                        await self._watch(windows)
            except (CommandError, TimeoutError, OSError) as error:
                self._say(str(error))
            await asyncio.sleep(RETRY_SECONDS)

    def _wait(self) -> None:
        """Log once that a window is still to come."""
        waiting = "waiting"
        if self._problem != waiting:
            self._problem = waiting
            log.info("Overlay menu: waiting for its window and Steam's")

    def _say(self, problem: str) -> None:
        """Log why the menu is not kept once, not on every try."""
        if problem != self._problem:
            self._problem = problem
            log.warning("Overlay menu not kept: %s", problem)

    async def _watch(self, windows: Windows) -> None:
        """Keep Steam's flag for these two windows until one of them is another."""
        menu = cardinals(await self._display.read(windows.menu, OVERLAY))
        steam = cardinals(await self._display.read(windows.steam, OVERLAY, INPUT_FOCUS))
        apps = cardinals(await self._display.read(None, FOCUSABLE_APPS))
        flag = _first(steam, OVERLAY)
        keeper = OverlayKeeper(
            menu=_first(menu, OVERLAY),
            steam=flag,
            own=steams_own(flag, _first(steam, INPUT_FOCUS), apps.get(FOCUSABLE_APPS, ())),
        )
        changes: asyncio.Queue[tuple[str, str, int] | None] = asyncio.Queue()
        readers = [
            asyncio.create_task(self._read("menu", windows.menu, (OVERLAY,), changes)),
            asyncio.create_task(
                self._read("steam", windows.steam, (OVERLAY, INPUT_FOCUS), changes)
            ),
        ]
        checked = self._now()
        try:
            while True:
                # A flag the menu left behind before the fix went on is taken off right away.
                wanted = keeper.wanted(self._now())
                if wanted is not None:
                    await self._display.write(windows.steam, OVERLAY, wanted)
                    keeper.written(wanted, self._now())
                    if not self._told:
                        self._told = True
                        log.info(
                            "Overlay menu kept in sight: Steam's window flag set to %d", wanted
                        )
                wait = keeper.due(self._now())
                try:
                    async with asyncio.timeout(RECHECK_SECONDS if wait is None else wait):
                        change = await changes.get()
                except TimeoutError:
                    change = None
                    if wait is not None:
                        continue
                if change is None:
                    # A reader ended, or it is time to look: go on only with the same windows.
                    if any(reader.done() for reader in readers):
                        return
                    if find_windows(await self._display.list_windows()) != windows:
                        return
                    checked = self._now()
                    continue
                self._take(keeper, change)
                if self._now() - checked >= RECHECK_SECONDS:
                    if find_windows(await self._display.list_windows()) != windows:
                        return
                    checked = self._now()
        finally:
            for reader in readers:
                reader.cancel()
            await asyncio.wait(readers)

    def _take(self, keeper: OverlayKeeper, change: tuple[str, str, int]) -> None:
        who, atom, value = change
        now = self._now()
        if who == "menu":
            keeper.menu_changed(value, now)
        elif atom == OVERLAY:
            keeper.steam_changed(value, now)
        else:
            keeper.steam_focus_changed(now)

    async def _read(
        self,
        who: str,
        window: int,
        atoms: tuple[str, ...],
        changes: asyncio.Queue[tuple[str, str, int] | None],
    ) -> None:
        """Pass on every change of the window's properties; None when the watch ends."""
        try:
            with suppress(CommandError, OSError):
                async with aclosing(self._display.spy(window, *atoms)) as lines:
                    # xprop first prints the properties as they are, one line each.
                    skip = len(atoms)
                    async for line in lines:
                        if skip > 0:
                            skip -= 1
                            continue
                        for atom, values in cardinals(line).items():
                            if values:
                                changes.put_nowait((who, atom, values[0]))
        finally:
            changes.put_nowait(None)


def _first(values: dict[str, tuple[int, ...]], atom: str) -> int:
    """A property's first number; 0 for one that is not set."""
    found = values.get(atom, ())
    return found[0] if found else 0
