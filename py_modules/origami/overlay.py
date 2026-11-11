# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""The overlay flags of Steam's window and of the system's overlay menu (B18).

On Bazzite a long press of the quick access button opens OpenGamepadUI's menu over Steam. A window
asks gamescope to show it over the rest with STEAM_OVERLAY = 1, and gamescope shows one such window.
The menu sets the flag on its own window as it opens and takes it off as it closes; closing, it
also sets it on Steam's window, and with no game running does not take it off there the next time
it opens. Two windows ask then, gamescope shows Steam's, and the menu opens unseen, though it
sounds and takes the buttons.

Steam sets the flag of its own window itself, together with its input focus, as its menus open
over a game. So the flag is kept as Steam last set it: taken off while the menu is open, put back
to Steam's own value once the menu has closed.
"""

import re
from dataclasses import dataclass
from pathlib import Path

OVERLAY = "STEAM_OVERLAY"
INPUT_FOCUS = "STEAM_INPUT_FOCUS"
FOCUSABLE_APPS = "GAMESCOPE_FOCUSABLE_APPS"
"""Root window property: the apps gamescope may give the focus, Steam among them."""
STEAM_APP = 769

MENU_PROCESS = "opengamepad-ui."
"""The menu's process, as the kernel cuts the name of opengamepad-ui.x86_64."""
MENU_CLASS = "Open Gamepad UI"
STEAM_CLASS = ("steamwebhelper", "steam")
"""Instance and class of Steam's main window; its helpers have other pairs."""
LISTER = Path("usr/bin/xwininfo")
"""The program that finds the two windows; without it the fix is not offered."""

NEAR_SECONDS = 0.15
"""A change of Steam's flag this close to a change of the menu's is the menu's doing."""
OWN_SECONDS = 0.05
"""Steam writes its input focus within a few ms of its own flag; the menu writes the flag alone."""
SETTLE_SECONDS = 0.2
"""How long after a change the flags are looked at: by then every change that belongs with it has
come in, in whichever order the two windows reported them."""
ECHO_SECONDS = 1.0

_WINDOW = re.compile(r'^\s*(0x[0-9a-f]+) .*\("([^"]*)" "([^"]*)"\)\s+(\d+)x(\d+)')
_CARDINAL = re.compile(r"^(\w+)\(CARDINAL\) =\s*(.*)$")


@dataclass(frozen=True, slots=True)
class Windows:
    menu: int
    steam: int


def menu_runs(root: Path) -> bool:
    """Whether the system's overlay menu runs here; it does on Bazzite's consoles in game mode."""
    try:
        entries = list((root / "proc").iterdir())
    except OSError:
        return False
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            name = (entry / "comm").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if name == MENU_PROCESS:
            return True
    return False


def find_windows(listing: str) -> Windows | None:
    """The menu's window and Steam's in xwininfo's list of the display's top windows.

    Steam's is the largest with its class: there is one, and helpers of a pixel or two.
    """
    menu: int | None = None
    steam: tuple[int, int] | None = None
    for line in listing.splitlines():
        found = _WINDOW.match(line)
        if found is None:
            continue
        window, pair = int(found[1], 16), (found[2], found[3])
        area = int(found[4]) * int(found[5])
        if pair[1] == MENU_CLASS and menu is None:
            menu = window
        elif pair == STEAM_CLASS and (steam is None or area > steam[1]):
            steam = (window, area)
    if menu is None or steam is None:
        return None
    return Windows(menu, steam[0])


def cardinals(output: str) -> dict[str, tuple[int, ...]]:
    """The CARDINAL properties in xprop's output by name; one that is not set is left out."""
    values: dict[str, tuple[int, ...]] = {}
    for line in output.splitlines():
        found = _CARDINAL.match(line.strip())
        if found is None:
            continue
        try:
            values[found[1]] = tuple(int(part) for part in found[2].split(",") if part.strip())
        except ValueError:
            continue
    return values


def steams_own(overlay: int, input_focus: int, focusable: tuple[int, ...]) -> int:
    """The flag Steam itself means for its window, told from how things stand.

    Steam asks to be shown over a game together with the input focus, and only while a game is
    there to be shown over. A flag without either is one the menu left behind.
    """
    game = any(app != STEAM_APP for app in focusable)
    return 1 if overlay == 1 and input_focus == 1 and game else 0


class OverlayKeeper:
    """Tells which flag Steam's window should have, from the changes of both windows' flags.

    Every change comes with its time. `wanted()` gives the flag to write once things have
    settled, and `written()` takes the write back in.
    """

    def __init__(self, *, menu: int, steam: int, own: int) -> None:
        self._menu = menu
        self._steam = steam
        self._own = own
        """The flag Steam last set itself."""
        self._menu_changes: list[float] = []
        self._undecided: list[tuple[float, int, bool]] = []
        """Changes of Steam's flag not yet told apart: time, value, whether Steam wrote it."""
        self._echo: tuple[int, float] | None = None

    @property
    def own(self) -> int:
        return self._own

    def menu_changed(self, value: int, now: float) -> None:
        self._menu = value
        self._menu_changes = [*self._menu_changes[-7:], now]

    def steam_changed(self, value: int, now: float) -> None:
        self._steam = value
        if self._echo is not None:
            echoed, until = self._echo
            self._echo = None
            if value == echoed and now <= until:
                return
        self._undecided.append((now, value, False))

    def steam_focus_changed(self, now: float) -> None:
        """Steam's input focus was written: a flag written just before it is Steam's own."""
        if self._undecided:
            at, value, _ = self._undecided[-1]
            if now - at <= OWN_SECONDS:
                self._undecided[-1] = (at, value, True)

    def due(self, now: float) -> float | None:
        """Seconds until `wanted()` may have an answer it has not now; None when nothing waits."""
        waits = [at + SETTLE_SECONDS - now for at, _, _ in self._undecided]
        if self._menu_changes:
            waits.append(self._menu_changes[-1] + SETTLE_SECONDS - now)
        ahead = [wait for wait in waits if wait > 0]
        return min(ahead) if ahead else None

    def wanted(self, now: float) -> int | None:
        """The flag to write on Steam's window now; None while it is right or not settled."""
        if self._menu_changes and now - self._menu_changes[-1] < SETTLE_SECONDS:
            return None
        if any(now - at < SETTLE_SECONDS for at, _, _ in self._undecided):
            return None
        for at, value, by_steam in self._undecided:
            near = any(abs(at - change) <= NEAR_SECONDS for change in self._menu_changes)
            if by_steam or not near:
                self._own = value
        self._undecided = []
        wanted = 0 if self._menu == 1 else self._own
        return None if wanted == self._steam else wanted

    def written(self, value: int, now: float) -> None:
        """ORIGAMI wrote the flag; its change comes back from the window and is not Steam's."""
        self._steam = value
        self._echo = (value, now + ECHO_SECONDS)
