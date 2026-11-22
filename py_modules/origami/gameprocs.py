# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""The processes of Steam's games and of its shader processing, as /proc shows them."""

import re
from collections.abc import Iterator
from pathlib import Path

STEAM_GAME = b"SteamAppId="
"""In the environment of every process of a game Steam started, and of no other."""
SHADER_PROGRAM = "fossilize"
"""Steam compiles a game's shaders in the background with fossilize_replay; a process name is cut
at 15 characters."""
SHADER_CACHE = re.compile(rb"/shadercache/(\d+)/")


def game_processes(root: Path) -> Iterator[tuple[Path, list[bytes]]]:
    """The processes of the games Steam started: each one's folder in /proc and its environment."""
    for environment in (root / "proc").glob("[0-9]*/environ"):
        try:
            variables = environment.read_bytes().split(b"\0")
        except OSError:
            # The process ended meanwhile.
            continue
        if any(item.startswith(STEAM_GAME) for item in variables):
            yield environment.parent, variables


def game_runs(root: Path) -> bool:
    return next(game_processes(root), None) is not None


def shader_work(root: Path) -> tuple[frozenset[int], bool]:
    """The games whose shader cache Steam is writing now, and whether there is such work whose
    game cannot be told."""
    games: set[int] = set()
    unknown = False
    for name in (root / "proc").glob("[0-9]*/comm"):
        try:
            if not name.read_text(encoding="utf-8", errors="replace").startswith(SHADER_PROGRAM):
                continue
            found = SHADER_CACHE.findall((name.parent / "cmdline").read_bytes())
        except OSError:
            # The process ended meanwhile.
            continue
        games.update(int(game) for game in found)
        unknown = unknown or not found
    return frozenset(games), unknown
