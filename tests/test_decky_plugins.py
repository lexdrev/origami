# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from pathlib import Path

from origami.decky_plugins import enabled_plugins


def install(home: Path, folder: str, name: str) -> None:
    manifest = home / "plugins" / folder / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"name": name, "flags": ["root"]}), encoding="utf-8")


def test_installed_plugins_except_the_ones_switched_off(tmp_path: Path) -> None:
    install(tmp_path, "HueSync", "HueSync")
    install(tmp_path, "ally-vibe-control", "Ally Vibe Control")
    install(tmp_path, "Origami", "ORIGAMI")
    settings = tmp_path / "settings" / "loader.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"disabled_plugins": ["HueSync"]}), encoding="utf-8")

    assert enabled_plugins(tmp_path) == {"Ally Vibe Control", "ORIGAMI"}


def test_without_decky_settings_every_plugin_counts(tmp_path: Path) -> None:
    install(tmp_path, "HueSync", "HueSync")
    (tmp_path / "plugins" / "broken").mkdir()
    (tmp_path / "plugins" / "broken" / "plugin.json").write_text("{", encoding="utf-8")

    assert enabled_plugins(tmp_path) == {"HueSync"}
