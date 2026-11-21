# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Other Decky plugins that drive the same hardware as ORIGAMI.

Decky keeps every plugin in its own folder with a plugin.json, and lists the ones the user
switched off by name in settings/loader.json ("disabled_plugins").
"""

import logging
from dataclasses import dataclass, fields
from pathlib import Path

from origami.jsonio import parse_object

log = logging.getLogger(__name__)

LIGHTING_OWNERS = ("HueSync", "Ally Center")
"""Plugins that drive the stick rings; while one runs, ORIGAMI leaves them alone."""
SATURATION_OWNERS = ("vibrantDeck",)
"""Plugins that write gamescope's colour gamut themselves, past Steam's own saturation setting."""
VIBRATION_OWNERS = ("Ally Vibe Control", "Ally Fix")
"""Plugins that set the strength of the handle vibration."""
TRIGGER_OWNERS = ("Ally Fix",)
"""Plugins that rumble the impulse triggers with a HID-BPF program of their own."""
POWER_OWNERS = ("Panel de Control", "SimpleDeckyTDP", "PowerTools", "PowerControl", "Ally Center")
"""Plugins that set the TDP or the CPU boost and frequency; ORIGAMI then shows the power only.
Ally Center has a switch that leaves the TDP to another plugin, but keeps its own CPU settings."""
BOOST_OWNERS = ("Ally Fix",)
"""Plugins that hold the CPU boost and its frequency cap but not the TDP (Ally Fix's CPU Boost Fix
keeps the boost off and the cap applied); ORIGAMI then keeps the TDP only."""
FAN_OWNERS = ("Panel de Control", "Ally Fix", "Fantastic", "PowerControl", "Ally Center")
"""Plugins that drive the fans; ORIGAMI then shows them only. Fantastic is made for the Steam Deck's
fan, but an owner of a ROG Ally had it on (2026-11-04), so the two never take turns. Ally Center's
fan modes write the platform profile, which switches a fan curve off."""
SOUND_OWNERS = ("Ally DSP",)
"""Plugins that put a filter of their own in front of the speakers; two would process the sound
twice, so ORIGAMI then leaves the speakers alone."""
SHARPNESS_OWNERS = ("vkBasalt Manager",)
"""Plugins that write vkBasalt's configuration in the user's home, which ORIGAMI's sharpness
writes too; ORIGAMI then leaves vkBasalt alone."""


@dataclass(frozen=True, slots=True)
class Launcher:
    """A plugin that starts its games through a wrapper of its own in their launch options."""

    plugin: str
    wrapper: str
    """The wrapper's file name, as a game's launch options have it."""
    sharpening: str
    """Where the plugin has a sharpening of its own: a key of the interface's texts."""


SHARPNESS_LAUNCHERS = (Launcher("MAKO - Frame Generation", "mako-run", "shaders"),)
"""Plugins whose wrapper builds a game's chain of Vulkan layers itself: it keeps vkBasalt out or
loads one of its own, so in their games the sharpness is theirs and ORIGAMI says whose."""
SHARPNESS_COMPANION = "Decky LSFG-VK"
"""A frame generation plugin in whose games ORIGAMI's sharpness works (seen on the console). The
screen names it as the way to have both, whether it is installed or not."""


@dataclass(frozen=True, slots=True)
class Conflicts:
    """Enabled plugins that drive hardware ORIGAMI also drives; ORIGAMI then leaves it alone."""

    lighting: str | None
    saturation: str | None
    vibration: str | None
    triggers: str | None
    power: str | None
    boost: str | None
    """The plugin that holds the CPU boost: one that sets the whole power, or the boost alone."""
    fans: str | None
    sound: str | None
    sharpness: str | None


def describe(conflicts: Conflicts) -> str:
    """The parts other plugins drive and who drives each, for one line of the log."""
    told = [
        f"{item.name} {owner}"
        for item in fields(conflicts)
        if (owner := getattr(conflicts, item.name)) is not None
    ]
    return ", ".join(told) or "nothing"


def read_conflicts(decky_home: Path) -> Conflicts:
    enabled = enabled_plugins(decky_home)

    def owner(names: tuple[str, ...]) -> str | None:
        return next((name for name in names if name in enabled), None)

    return Conflicts(
        lighting=owner(LIGHTING_OWNERS),
        saturation=owner(SATURATION_OWNERS),
        vibration=owner(VIBRATION_OWNERS),
        triggers=owner(TRIGGER_OWNERS),
        power=owner(POWER_OWNERS),
        boost=owner(POWER_OWNERS + BOOST_OWNERS),
        fans=owner(FAN_OWNERS),
        sound=owner(SOUND_OWNERS),
        sharpness=owner(SHARPNESS_OWNERS),
    )


def launcher_in(launch_options: str) -> Launcher | None:
    """The plugin whose wrapper a game's launch options run; None when ORIGAMI knows none."""
    return next(
        (launcher for launcher in SHARPNESS_LAUNCHERS if launcher.wrapper in launch_options), None
    )


def enabled_plugins(decky_home: Path) -> frozenset[str]:
    """Names of the plugins that are installed and not switched off."""
    installed: set[str] = set()
    for manifest in sorted((decky_home / "plugins").glob("*/plugin.json")):
        try:
            name = parse_object(manifest.read_text(encoding="utf-8")).get("name")
        except (OSError, ValueError) as error:
            log.debug("Skipping unreadable %s: %s", manifest, error)
            continue
        if isinstance(name, str):
            installed.add(name)
    return frozenset(installed - _disabled(decky_home))


def _disabled(decky_home: Path) -> set[str]:
    try:
        settings = parse_object(
            (decky_home / "settings" / "loader.json").read_text(encoding="utf-8")
        )
    except FileNotFoundError:
        return set()
    except (OSError, ValueError) as error:
        log.warning("Cannot read Decky's settings: %s", error)
        return set()
    names = settings.get("disabled_plugins")
    return {name for name in names if isinstance(name, str)} if isinstance(names, list) else set()
