# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from pathlib import Path

import pytest

from origami.buttons import ButtonAction
from origami.fans import FanCurve
from origami.lighting import Lighting, LightMode
from origami.power import GamePower, Power
from origami.settings import FIRST_TAB, SOUNDTRACKS_TAB, Language, Settings, SettingsStore
from origami.triggers import TriggerLevel, TriggerRumble, Triggers
from origami.vibration import Vibration


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
        {"saturation": 201},
        {"saturation": True},
        {"armoury_crate": "dance"},
        {"armoury_crate_hold": "l5"},
    ],
)
def test_update_rejects_invalid_changes(changes: dict[str, object]) -> None:
    with pytest.raises(
        ValueError, match=r"theme|de|qam_tab|position|qam_assist|Saturation|ButtonAction|L5"
    ):
        Settings().updated(changes)


def test_own_tab_settings_are_saved(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    settings = Settings(qam_tab=False, qam_tab_before=None)

    store.save(settings)

    assert store.load() == settings


def test_qam_assist_is_off_until_switched_on(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    assert Settings().qam_assist is None

    store.save(Settings().updated({"qam_assist": True}))

    assert store.load() == Settings(qam_assist=True)


def test_fixes_stay_unset_until_the_user_sets_them_and_off_is_kept(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    unset = Settings()
    fixes = (unset.qam_assist, unset.gyro_fix, unset.armoury_crate, unset.armoury_crate_hold)
    assert fixes == (None, None, None, None)
    store.save(unset)
    assert store.load() == unset

    store.save(unset.updated({"qam_assist": False, "gyro_fix": False, "armoury_crate": "none"}))

    loaded = store.load()
    assert (loaded.qam_assist, loaded.gyro_fix, loaded.armoury_crate) == (
        False,
        False,
        ButtonAction.NONE,
    )
    assert loaded.armoury_crate_hold is None


def test_restored_settings_leave_the_system_and_keep_the_interface_and_tdp() -> None:
    game = GamePower(1091500, "Cyberpunk 2077", Power(tdp=25, cpu_boost=True))
    chosen = Settings().updated(
        {
            "language": "en",
            "qam_tab_before": FIRST_TAB,
            "qam_assist": True,
            "gyro_fix": False,
            "armoury_crate": "origami",
            "lighting": {"mode": "static"},
            "saturation": 150,
            "trigger_rumble": {"enabled": True},
            "power": {"tdp": 20, "cpu_boost": False},
            "battery_high_tdp": True,
            "game_power": [game.to_json()],
            "fans": {"enabled": True},
        }
    )

    assert chosen.restored() == Settings(
        language=Language.EN,
        qam_tab_before=FIRST_TAB,
        vibration=None,
        manage_tdp=None,
        power=Power(tdp=20),
        battery_high_tdp=True,
        game_power=(GamePower(1091500, "Cyberpunk 2077", Power(tdp=25)),),
    )


def test_lighting_is_unset_until_chosen_and_then_saved(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    assert Settings().lighting is None

    store.save(Settings().updated({"lighting": {"mode": "breathing", "left": 0xFF0000}}))

    assert store.load() == Settings(lighting=Lighting(mode=LightMode.BREATHING, left=0xFF0000))


def test_bad_lighting_is_rejected() -> None:
    with pytest.raises(ValueError, match="mode"):
        Settings().updated({"lighting": {"mode": "disco"}})


def test_vibration_starts_at_the_middle_and_is_saved(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    assert Settings().vibration == Vibration(enabled=True, left=50, right=50)
    # Saved before the default: the controller keeps its own strength.
    assert Settings().updated({"vibration": None}).vibration is None

    store.save(Settings().updated({"vibration": {"left": 25, "right": 75}}))

    assert store.load() == Settings(vibration=Vibration(left=25, right=75))


def test_bad_vibration_is_rejected() -> None:
    with pytest.raises(ValueError, match="left"):
        Settings().updated({"vibration": {"left": 101, "right": 50}})


def test_trigger_rumble_is_unset_until_chosen_and_then_saved(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    assert Settings().trigger_rumble is None

    store.save(
        Settings().updated(
            {"trigger_rumble": {"enabled": True, "triggers": "both", "level": "strong"}}
        )
    )

    assert store.load() == Settings(
        trigger_rumble=TriggerRumble(True, Triggers.BOTH, TriggerLevel.STRONG)
    )


def test_bad_trigger_rumble_is_rejected() -> None:
    with pytest.raises(ValueError, match="TriggerLevel"):
        Settings().updated({"trigger_rumble": {"triggers": "right", "level": "loud"}})


def test_armoury_crate_actions_are_saved(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    changes = {"armoury_crate": "origami", "armoury_crate_hold": "quick_access"}

    store.save(Settings().updated(changes))

    loaded = store.load()
    assert (loaded.armoury_crate, loaded.armoury_crate_hold) == (
        ButtonAction.ORIGAMI,
        ButtonAction.QUICK_ACCESS,
    )


def test_origami_owns_the_tdp_at_the_factorys_limits_until_changed(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    assert Settings().manage_tdp is True
    assert Settings().power == Power(17, headroom=True, cpu_boost=None)
    assert Settings().battery_high_tdp is False

    changes = {
        "power": {"tdp": 25, "headroom": False, "cpu_boost": False},
        "manage_tdp": False,
        "battery_high_tdp": True,
    }
    store.save(Settings().updated(changes))

    assert store.load() == Settings(
        manage_tdp=False, power=Power(25, headroom=False, cpu_boost=False), battery_high_tdp=True
    )


def test_the_tdp_left_to_steam_by_restoring_stays_undecided_until_the_user_sets_it(
    tmp_path: Path,
) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    store.save(Settings().restored())

    assert store.load().manage_tdp is None
    assert store.load().updated({"manage_tdp": False}).manage_tdp is False


def test_games_keep_their_own_power_through_a_save(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    game = {
        "app_id": 1920490,
        "name": "  The Outer Worlds  ",
        "power": {"tdp": 15, "cpu_boost": True},
    }
    waiting = {"app_id": 7, "name": "Other", "power": {"tdp": 25}, "active": False}

    store.save(Settings(power=Power(20)).updated({"game_power": [game, waiting]}))
    loaded = store.load()

    assert loaded.game_power == (
        GamePower(1920490, "The Outer Worlds", Power(15, headroom=True, cpu_boost=True)),
        GamePower(7, "Other", Power(25), active=False),
    )
    assert loaded.power_for(1920490) == Power(15, headroom=True, cpu_boost=True)
    # A game whose profile waits, a game without one and no game at all run the general settings.
    assert loaded.power_for(7) == loaded.power_for(42) == loaded.power_for(None) == Power(20)


def test_bad_game_power_is_rejected() -> None:
    game = {"app_id": 1, "name": "Game", "power": {"tdp": 15}}
    with pytest.raises(ValueError, match="list"):
        Settings().updated({"game_power": game})
    with pytest.raises(ValueError, match="only one"):
        Settings().updated({"game_power": [game, game]})
    with pytest.raises(ValueError, match="app id"):
        Settings().updated({"game_power": [{**game, "app_id": True}]})
    with pytest.raises(ValueError, match="name"):
        Settings().updated({"game_power": [{**game, "name": " "}]})
    with pytest.raises(ValueError, match="tdp"):
        Settings().updated({"game_power": [{**game, "power": {"tdp": 50}}]})


def test_the_fan_curve_stays_off_until_switched_on_and_keeps_its_points(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    assert Settings().fans is None

    store.save(
        Settings().updated({"fans": {"enabled": False, "points": [20, 30, 45, 60, 75, 90, 100]}})
    )

    assert store.load().fans == FanCurve(enabled=False, points=(20, 30, 45, 60, 75, 90, 100))


def test_bad_power_settings_are_rejected() -> None:
    with pytest.raises(ValueError, match="tdp"):
        Settings().updated({"power": {"tdp": 40}})
    with pytest.raises(ValueError, match="manage_tdp"):
        Settings().updated({"manage_tdp": 1})
