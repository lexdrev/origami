# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from pathlib import Path

from origami.decky_plugins import POWER_OWNERS, enabled_plugins, read_conflicts


def install(home: Path, folder: str, name: str) -> None:
    manifest = home / "plugins" / folder / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"name": name, "flags": ["root"]}), encoding="utf-8")


def test_installed_plugins_except_the_ones_switched_off(tmp_path: Path) -> None:
    install(tmp_path, "lights", "Lights")
    install(tmp_path, "rumble-control", "Rumble Control")
    install(tmp_path, "Origami", "ORIGAMI")
    settings = tmp_path / "settings" / "loader.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"disabled_plugins": ["Lights"]}), encoding="utf-8")

    assert enabled_plugins(tmp_path) == {"Rumble Control", "ORIGAMI"}


def test_without_decky_settings_every_plugin_counts(tmp_path: Path) -> None:
    install(tmp_path, "lights", "Lights")
    (tmp_path / "plugins" / "broken").mkdir()
    (tmp_path / "plugins" / "broken" / "plugin.json").write_text("{", encoding="utf-8")

    assert enabled_plugins(tmp_path) == {"Lights"}


def test_a_power_plugin_holds_the_boost_too(tmp_path: Path) -> None:
    install(tmp_path, "pdc", POWER_OWNERS[0])

    conflicts = read_conflicts(tmp_path)

    assert (conflicts.power, conflicts.boost) == (POWER_OWNERS[0], POWER_OWNERS[0])


def test_ally_fix_holds_the_boost_and_fantastic_the_fans(tmp_path: Path) -> None:
    install(tmp_path, "Ally Fix", "Ally Fix")
    install(tmp_path, "Fantastic", "Fantastic")

    conflicts = read_conflicts(tmp_path)

    assert (conflicts.power, conflicts.boost, conflicts.fans) == (None, "Ally Fix", "Ally Fix")
    (tmp_path / "plugins" / "Ally Fix" / "plugin.json").unlink()
    assert read_conflicts(tmp_path).fans == "Fantastic"


def test_ally_center_holds_the_power_the_fans_and_the_lighting(tmp_path: Path) -> None:
    install(tmp_path, "allycenter", "Ally Center")

    conflicts = read_conflicts(tmp_path)

    owners = (conflicts.power, conflicts.boost, conflicts.fans, conflicts.lighting)
    assert owners == ("Ally Center",) * 4
    assert (conflicts.saturation, conflicts.vibration, conflicts.triggers) == (None, None, None)


def test_power_control_holds_the_power_and_the_fans(tmp_path: Path) -> None:
    install(tmp_path, "PowerControl", "PowerControl")

    conflicts = read_conflicts(tmp_path)

    assert (conflicts.power, conflicts.boost, conflicts.fans) == ("PowerControl",) * 3
    assert conflicts.lighting is None
