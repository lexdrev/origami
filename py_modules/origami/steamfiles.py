# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""What Steam writes down of the games it has: its libraries, their manifests, the shortcuts.

Steam keeps these in its own text format (nested "key" "value" pairs), and the shortcuts to
non-Steam games in a binary one.
"""

import re
from dataclasses import dataclass
from pathlib import Path

type Vdf = dict[str, str | Vdf]

STEAM_FOLDERS = (Path(".local/share/Steam"), Path(".steam/steam"))
"""Where Steam lives in a user's home; the second is its own link to the first."""
LIBRARIES = Path("steamapps/libraryfolders.vdf")
TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])|//[^\n]*')
ESCAPED = re.compile(r"\\(.)")
ESCAPES = {"n": "\n", "t": "\t"}
SHORTCUTS_START = b"\x00shortcuts\x00"
SHORTCUT = re.compile(rb"\x02appid\x00(.{4})", re.DOTALL | re.IGNORECASE)
SHORTCUT_TEXT = re.compile(rb"\x01(appname|exe|startdir)\x00([^\x00]*)\x00", re.IGNORECASE)
FIRST_SHORTCUT_ID = 2**31
"""Steam gives its shortcuts ids from here up; the games of its store are below."""


def parse_vdf(text: str) -> Vdf:
    """Parse Steam's text format; raise ValueError when the text is not in it."""
    root: Vdf = {}
    stack = [root]
    key: str | None = None
    position = 0
    for token in TOKEN.finditer(text):
        if text[position : token.start()].strip():
            raise ValueError("text outside quotes")
        position = token.end()
        word, brace = token.group(1), token.group(2)
        if word is not None:
            word = ESCAPED.sub(lambda escape: ESCAPES.get(escape[1], escape[1]), word)
            if key is None:
                key = word
            else:
                stack[-1][key] = word
                key = None
        elif brace == "{":
            if key is None:
                raise ValueError("a block without a name")
            block: Vdf = {}
            stack[-1][key] = block
            stack.append(block)
            key = None
        elif brace == "}":
            if key is not None or len(stack) == 1:
                raise ValueError("a block closed out of place")
            stack.pop()
    if text[position:].strip() or key is not None or len(stack) != 1:
        raise ValueError("unfinished text")
    return root


def child(vdf: Vdf, name: str) -> str | Vdf | None:
    """What a block holds under a name, whatever the case Steam wrote the name in."""
    return next((value for key, value in vdf.items() if key.lower() == name), None)


def block(vdf: Vdf, name: str) -> Vdf:
    """A named block; raise ValueError when it is not there."""
    value = child(vdf, name)
    if not isinstance(value, dict):
        raise ValueError(f'no "{name}" block')
    return value


def text(vdf: Vdf, name: str) -> str:
    """A named value; raise ValueError when it is not there."""
    value = child(vdf, name)
    if not isinstance(value, str):
        raise ValueError(f'no "{name}" value')
    return value


def steam_folder(home: Path) -> Path | None:
    """Steam's folder in this home; None where Steam has no libraries written down."""
    for folder in STEAM_FOLDERS:
        if (home / folder / LIBRARIES).is_file():
            return home / folder
    return None


@dataclass(frozen=True, slots=True)
class Library:
    """A folder Steam installs games into, as Steam's own list has it."""

    path: Path
    apps: frozenset[int]
    """The games Steam installed there, known also while the folder is not mounted."""


def read_libraries(steam: Path) -> list[Library]:
    """Steam's libraries; raise OSError or ValueError when its list cannot be read."""
    listed = block(parse_vdf((steam / LIBRARIES).read_text(encoding="utf-8")), "libraryfolders")
    libraries: list[Library] = []
    for value in listed.values():
        if not isinstance(value, dict):
            continue
        # A library Steam has just added has no games listed yet.
        apps = child(value, "apps")
        games = apps if isinstance(apps, dict) else {}
        libraries.append(
            Library(
                Path(text(value, "path")), frozenset(int(app) for app in games if app.isdecimal())
            )
        )
    if not libraries:
        raise ValueError("Steam lists no library")
    return libraries


@dataclass(frozen=True, slots=True)
class Manifest:
    """An installed game, as its manifest in a library tells of it."""

    app_id: int
    name: str
    folder: str
    """The game's folder in the library's "common"."""


def read_manifest(path: Path) -> Manifest:
    """Raise OSError or ValueError when the manifest cannot be read."""
    state = block(parse_vdf(path.read_text(encoding="utf-8", errors="replace")), "appstate")
    return Manifest(int(text(state, "appid")), text(state, "name"), text(state, "installdir"))


@dataclass(frozen=True, slots=True)
class Shortcut:
    """A non-Steam game the user added to Steam."""

    app_id: int
    name: str
    paths: tuple[str, ...]
    """Its program and the folder it starts in."""


def parse_shortcuts(data: bytes) -> list[Shortcut]:
    """Parse a shortcuts.vdf; raise ValueError when the data is not one."""
    if not data.startswith(SHORTCUTS_START):
        raise ValueError("not Steam's shortcuts")
    starts = list(SHORTCUT.finditer(data))
    shortcuts: list[Shortcut] = []
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(data)
        fields: dict[bytes, str] = {}
        for field in SHORTCUT_TEXT.finditer(data, start.end(), end):
            fields.setdefault(field[1].lower(), field[2].decode(errors="replace"))
        shortcuts.append(
            Shortcut(
                int.from_bytes(start[1], "little"),
                fields.get(b"appname", ""),
                tuple(
                    path.strip('"')
                    for path in (fields.get(b"exe", ""), fields.get(b"startdir", ""))
                    if path.strip('"')
                ),
            )
        )
    return shortcuts
