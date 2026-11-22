# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

import pytest

from origami.steamfiles import (
    Shortcut,
    parse_shortcuts,
    parse_vdf,
    read_libraries,
    read_manifest,
    steam_folder,
)

from fakes import FakeSteam, shortcuts_vdf


def test_steam_s_text_format_is_read_with_its_blocks_and_escapes() -> None:
    text = (
        '"Root"\n{\n\t"name"\t\t"Game \\"Two\\""\n\t// a note\n\t"inner"\n\t{\n'
        '\t\t"path"\t"C:\\\\Games"\n\t}\n\t"empty"\n\t{\n\t}\n}\n'
    )

    assert parse_vdf(text) == {
        "Root": {"name": 'Game "Two"', "inner": {"path": "C:\\Games"}, "empty": {}}
    }


@pytest.mark.parametrize(
    "text",
    [
        '"Root" { "name" "unfinished"',
        '"Root" { } }',
        '"Root" { "key" }',
        '{ "name" "value" }',
        '"Root" { name "value" }',
        '"Root"',
    ],
)
def test_text_that_is_not_in_steam_s_format_is_refused(text: str) -> None:
    with pytest.raises(ValueError):
        parse_vdf(text)


def test_the_libraries_come_with_the_games_steam_listed_in_them(tmp_path: Path) -> None:
    steam = FakeSteam(tmp_path / "home")
    card = steam.library(tmp_path / "card", mounted=False)
    steam.install(10, "First")
    steam.install(20, "On the card", card)

    libraries = read_libraries(steam.folder)

    assert [(library.path, library.apps) for library in libraries] == [
        (steam.folder, frozenset({10})),
        (card, frozenset({20})),
    ]
    assert steam_folder(tmp_path / "home") == steam.folder
    assert steam_folder(tmp_path / "elsewhere") is None


def test_a_list_without_libraries_is_refused(tmp_path: Path) -> None:
    steam = FakeSteam(tmp_path / "home")
    (steam.folder / "steamapps" / "libraryfolders.vdf").write_text('"libraryfolders"\n{\n}\n')

    with pytest.raises(ValueError):
        read_libraries(steam.folder)


def test_a_manifest_tells_the_game_its_name_and_its_folder(tmp_path: Path) -> None:
    steam = FakeSteam(tmp_path / "home")
    steam.install(617290, "Remnant: From the Ashes", folder="Remnant")

    manifest = read_manifest(steam.folder / "steamapps" / "appmanifest_617290.acf")

    assert (manifest.app_id, manifest.name, manifest.folder) == (
        617290,
        "Remnant: From the Ashes",
        "Remnant",
    )


def test_the_shortcuts_come_with_their_ids_names_and_paths() -> None:
    data = shortcuts_vdf(
        (3293947715, "Other Game", "/games/other/run.exe"), (2500000000, "Tool", "/opt/tool")
    )

    assert parse_shortcuts(data) == [
        Shortcut(3293947715, "Other Game", ("/games/other/run.exe", "/games/other")),
        Shortcut(2500000000, "Tool", ("/opt/tool", "/opt")),
    ]
    assert parse_shortcuts(shortcuts_vdf()) == []


def test_data_that_is_not_steam_s_shortcuts_is_refused() -> None:
    with pytest.raises(ValueError):
        parse_shortcuts(b"")
    with pytest.raises(ValueError):
        parse_shortcuts(b'"shortcuts"\n{\n}\n')
