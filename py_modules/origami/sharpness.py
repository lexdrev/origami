# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Sharper games: contrast adaptive sharpening (CAS), as Radeon Image Sharpening does on Windows.

vkBasalt is a Vulkan layer that runs AMD's CAS shader on a game's own frames, before gamescope
scales them. Bazzite has it in its image and SteamOS does not, so ORIGAMI brings its own build of
it, for 64-bit and 32-bit games, and loads that on both.

A system's own vkBasalt loads only into a process started with ENABLE_VKBASALT=1. Set for the
whole session, that variable reaches gamescope too, which then composites every frame and never
scans a game's frame out directly. So ORIGAMI sets no variable: it puts manifests of its build,
without a condition, among the user's layers, where the loader looks first; a system's manifest
of the same layer is dropped as a duplicate. The manifests and vkBasalt's configuration are there
only while a game starts and runs, so nothing else loads the layer.

vkBasalt reads its configuration once, as the game creates its Vulkan instance: a change reaches
a game the next time it starts.
"""

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

from origami.games import parse_game
from origami.jsonio import JsonValue, expect_bool

LAYER = "VK_LAYER_VKBASALT_post_processing"
LIBRARY = "libvkbasalt.so"
BUILDS = {"64": "lib64", "32": "lib32"}
"""ORIGAMI's builds of the layer: for 64-bit and for 32-bit games, as a manifest names the
two kinds, and the folder each build is in."""
MAX_STRENGTH = 100
OWN_CONFIG = "# ORIGAMI writes this file as a game starts and takes it away as the game ends."
"""The first line of the configuration ORIGAMI writes, by which it knows its own file."""
NEVER_PRESSED = "F35"
"""A key no keyboard has: vkBasalt switches its effects on a key press, Home unless told."""
SETS_VKBASALT = re.compile(r"\b(?:ENABLE_VKBASALT|DISABLE_VKBASALT|VKBASALT_CONFIG_FILE)=")
"""An assignment of one of vkBasalt's own variables, in launch options or in a script."""
HOME_SPELLINGS = ("$HOME/", "${HOME}/")
"""The user's home in launch options, besides "~/"."""
OWN_STRENGTH = re.compile(r"^casSharpness = (\d\.\d\d)$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Sharpness:
    """What the user chose for the sharpness; the defaults are its first values."""

    enabled: bool = True
    strength: int = 40
    """Percent of CAS's sharpness range; 40 is vkBasalt's own default. CAS sharpens at 0 too."""

    @classmethod
    def from_json(cls, value: object) -> Sharpness:
        """Parse the sharpness sent by the frontend or saved; raise ValueError on bad input."""
        if not isinstance(value, dict):
            raise ValueError("sharpness must be an object")
        data = cast("dict[str, object]", value)
        defaults = cls()
        strength = data.get("strength", defaults.strength)
        if (
            not isinstance(strength, int)
            or isinstance(strength, bool)
            or not 0 <= strength <= MAX_STRENGTH
        ):
            raise ValueError(f"strength must be a percentage from 0 to {MAX_STRENGTH}")
        return cls(
            enabled=expect_bool("enabled", data.get("enabled", defaults.enabled)),
            strength=strength,
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {"enabled": self.enabled, "strength": self.strength}


@dataclass(frozen=True, slots=True)
class GameSharpness:
    """A game's own sharpness, made as a copy of the general one when it is first chosen."""

    app_id: int
    """Steam's app id; non-Steam shortcuts have one as well."""
    name: str
    """The game's name as Steam showed it, for the list while the game is not running."""
    sharpness: Sharpness
    active: bool = True
    """The game starts with this sharpness; off, it starts with the general one and this waits."""

    @classmethod
    def from_json(cls, value: object) -> GameSharpness:
        """Parse a game's sharpness sent by the frontend or saved; raise ValueError on bad input."""
        data, app_id, name, active = parse_game(value, "sharpness")
        return cls(
            app_id=app_id,
            name=name,
            sharpness=Sharpness.from_json(data.get("sharpness")),
            active=active,
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "app_id": self.app_id,
            "name": self.name,
            "sharpness": self.sharpness.to_json(),
            "active": self.active,
        }


class GameState(StrEnum):
    """How the sharpness stands in the game that runs now, for the screen."""

    NO_GAME = "no_game"
    WORKING = "working"
    """The layer is in the game, with the sharpness set now."""
    OFF = "off"
    """Switched off for this game, and the layer is not in it."""
    TURNING_ON = "turning_on"
    """Switched on after the game started: the game gets the layer when it starts next."""
    TURNING_OFF = "turning_off"
    """Switched off after the game started: the game keeps the layer until it starts next."""
    NEW_STRENGTH = "new_strength"
    """The strength changed after the game started: the game takes it when it starts next."""
    MISSING = "missing"
    """On since before the game started, yet the layer is not in it: the game does not draw
    through Vulkan, or has not created its instance yet."""
    MANAGED = "managed"
    """The game's launch options set vkBasalt's variables themselves, or a wrapper in them does
    that builds the game's own chain of layers: the sharpness in this game is theirs."""


def game_state(
    *, wanted: Sharpness | None, started: Sharpness | None, known: bool, loaded: bool
) -> GameState:
    """The state of a running game whose vkBasalt is ORIGAMI's to set.

    `wanted` is the sharpness set for it now, `started` the one it started with, which ORIGAMI
    knows only when it saw the game start (`known`), and `loaded` whether the layer is in it.
    """
    on = wanted is not None and wanted.enabled
    if not on:
        return GameState.TURNING_OFF if loaded else GameState.OFF
    was_on = started is not None and started.enabled
    if not loaded:
        return GameState.MISSING if known and was_on else GameState.TURNING_ON
    if known and started != wanted:
        return GameState.NEW_STRENGTH
    return GameState.WORKING


def manifest_text(library: Path, bits: str) -> str:
    """The manifest of ORIGAMI's build of the layer for 64-bit or for 32-bit programs.

    The layer is enabled wherever the manifest is found: it has no condition. What switches it
    off (DISABLE_VKBASALT=1) is kept, for a game that must not have it. A loader of the other
    kind skips the manifest by its `library_arch` and takes the one for its own.
    """
    layer: dict[str, JsonValue] = {
        "name": LAYER,
        "type": "GLOBAL",
        "library_path": str(library),
        "library_arch": bits,
        "api_version": "1.3.223",
        "implementation_version": "1",
        "description": "ORIGAMI's sharpness: vkBasalt",
        "functions": {
            "vkGetInstanceProcAddr": "vkBasalt_GetInstanceProcAddr",
            "vkGetDeviceProcAddr": "vkBasalt_GetDeviceProcAddr",
        },
        "disable_environment": {"DISABLE_VKBASALT": "1"},
    }
    return json.dumps({"file_format_version": "1.2.1", "layer": layer}, indent=2) + "\n"


def config_text(sharpness: Sharpness) -> str:
    """vkBasalt's configuration for this sharpness: CAS alone, on from the game's first frame."""
    return "\n".join(
        (
            OWN_CONFIG,
            "effects = cas",
            f"casSharpness = {sharpness.strength / MAX_STRENGTH:.2f}",
            f"toggleKey = {NEVER_PRESSED}",
            "enableOnLaunch = True",
            "depthCapture = off",
            "",
        )
    )


def own_config(text: str) -> bool:
    """Whether a vkBasalt configuration is exactly as ORIGAMI wrote it.

    A file that somebody changed afterwards is theirs, whatever of ORIGAMI's lines it still holds:
    another program may merge its own settings into the file it finds.
    """
    strength = OWN_STRENGTH.search(text)
    if strength is None:
        return False
    percent = round(float(strength[1]) * MAX_STRENGTH)
    return 0 <= percent <= MAX_STRENGTH and text == config_text(Sharpness(strength=percent))


def sets_vkbasalt(text: str) -> bool:
    """Whether launch options, or a script they run, assign vkBasalt's own variables.

    Naming a variable is not enough: a script that only unsets them leaves vkBasalt alone.
    """
    return SETS_VKBASALT.search(text) is not None


def launch_programs(options: str) -> list[str]:
    """The programs Steam's launch options run in front of the game, as they are written.

    The words before %command% that are paths, quoted or not; the home, however it is written,
    comes back as "~". Variables are not programs.
    """
    programs: list[str] = []
    for word in options.split("%command%", 1)[0].split():
        path = word.strip("\"'")
        for home in HOME_SPELLINGS:
            if path.startswith(home):
                path = "~/" + path[len(home) :]
                break
        if path.startswith(("/", "~/")):
            programs.append(path)
    return programs
