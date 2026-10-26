# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from pathlib import Path

import pytest

from origami.settings import FIRST_TAB, SOUNDTRACKS_TAB, Language, Settings, SettingsStore


def test_defaults_when_there_is_no_file(tmp_path: Path) -> None:
    assert SettingsStore(tmp_path / "settings.json").load() == Settings()


def test_saved_settings_load_back(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")

    store.save(Settings(language=Language.RU))

    assert SettingsStore(tmp_path / "settings.json").load() == Settings(language=Language.RU)
    assert [path.name for path in tmp_path.iterdir()] == ["settings.json"]


def test_keys_from_a_newer_version_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"version": 9, "language": "en", "future": True}), encoding="utf-8")

    assert SettingsStore(path).load() == Settings(language=Language.EN)


@pytest.mark.parametrize("content", ["{", "[]", '{"language": "de"}', '{"language": 1}'])
def test_unreadable_file_falls_back_to_defaults(
    tmp_path: Path, content: str, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "settings.json"
    path.write_text(content, encoding="utf-8")

    assert SettingsStore(path).load() == Settings()
    assert "Ignoring unreadable settings" in caplog.text


def test_update_changes_only_the_given_field() -> None:
    assert Settings().updated({"language": "ru"}) == Settings(language=Language.RU)
    assert Settings(language=Language.RU).updated({}) == Settings(language=Language.RU)


def test_own_tab_is_on_above_soundtracks_by_default() -> None:
    assert Settings().qam_tab is True
    assert Settings().qam_tab_before == SOUNDTRACKS_TAB


@pytest.mark.parametrize("before", [FIRST_TAB, 0, 999, 5260355, None])
def test_own_tab_position(before: int | None) -> None:
    assert Settings().updated({"qam_tab_before": before}).qam_tab_before == before


@pytest.mark.parametrize(
    "changes",
    [
        {"language": "de"},
        {"theme": "light"},
        {"qam_tab": 1},
        {"qam_tab_before": -2},
        {"qam_tab_before": True},
        {"qam_tab_before": "7"},
        {"qam_assist": "yes"},
    ],
)
def test_update_rejects_invalid_changes(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError, match=r"theme|de|qam_tab|position|qam_assist"):
        Settings().updated(changes)


def test_own_tab_settings_are_saved(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    settings = Settings(qam_tab=False, qam_tab_before=None)

    store.save(settings)

    assert store.load() == settings


def test_qam_assist_is_off_until_switched_on(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    assert Settings().qam_assist is False

    store.save(Settings().updated({"qam_assist": True}))

    assert store.load() == Settings(qam_assist=True)
