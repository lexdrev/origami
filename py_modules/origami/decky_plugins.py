# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Other Decky plugins that drive the same hardware as ORIGAMI.

Decky keeps every plugin in its own folder with a plugin.json, and lists the ones the user
switched off by name in settings/loader.json ("disabled_plugins").
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from origami.jsonio import parse_object

log = logging.getLogger(__name__)

LIGHTING_OWNERS = ("HueSync",)
"""Plugins that drive the stick rings; while one runs, ORIGAMI leaves them alone."""
SATURATION_OWNERS = ("vibrantDeck",)
"""Plugins that write gamescope's colour gamut themselves, past Steam's own saturation setting."""
VIBRATION_OWNERS = ("Ally Vibe Control", "Ally Fix")
"""Plugins that set the strength of the handle vibration."""
TRIGGER_OWNERS = ("Ally Fix",)
"""Plugins that rumble the impulse triggers with a HID-BPF program of their own."""
POWER_OWNERS = ("Panel de Control", "SimpleDeckyTDP", "PowerTools")
"""Plugins that set the TDP or the CPU boost and frequency; ORIGAMI then shows the power only."""
FAN_OWNERS = ("Panel de Control", "Ally Fix")
"""Plugins that write the fan curves; ORIGAMI then shows the fans only."""


@dataclass(frozen=True, slots=True)
class Conflicts:
    """Enabled plugins that drive hardware ORIGAMI also drives; ORIGAMI then leaves it alone."""

    lighting: str | None
    saturation: str | None
    vibration: str | None
    triggers: str | None
    power: str | None
    fans: str | None


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
        fans=owner(FAN_OWNERS),
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
