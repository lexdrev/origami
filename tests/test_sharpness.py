# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import json
import shutil
from pathlib import Path

import pytest

from origami.blocks import Context
from origami.blocks import sharpness as sharpness_block
from origami.blocks.sharpness import (
    CONFIG,
    JOURNAL,
    MANIFEST,
    SYSTEM_MANIFEST,
    SharpnessBlock,
    layer_loaded,
)
from origami.decky_plugins import SHARPNESS_LAUNCHERS, Conflicts
from origami.journal import ChangeJournal
from origami.settings import Settings
from origami.sharpness import (
    LAYER,
    GameSharpness,
    GameState,
    Sharpness,
    config_text,
    game_state,
    launch_programs,
    library_64,
    manifest_text,
    own_config,
    sets_vkbasalt,
)

from fakes import VKBASALT_MANIFEST as SYSTEM
from fakes import FakeUser

GAME = 1920490
LAUNCHER = SHARPNESS_LAUNCHERS[0]
"""A plugin whose launch wrapper keeps the sharpness in its games."""
OTHER = 7


def test_sharpness_settings_parse_and_keep_their_defaults() -> None:
    assert Sharpness.from_json({}) == Sharpness(enabled=True, strength=40)
    chosen = Sharpness(enabled=False, strength=70)
    assert Sharpness.from_json(chosen.to_json()) == chosen
    assert Settings().updated({"sharpness": {"strength": 0}}).sharpness == Sharpness(strength=0)
    assert Settings().updated({"sharpness": None}).sharpness is None


@pytest.mark.parametrize(
    "value", ["on", {"strength": 101}, {"strength": -1}, {"strength": True}, {"enabled": 1}]
)
def test_sharpness_settings_refuse_bad_values(value: object) -> None:
    with pytest.raises(ValueError):
        Sharpness.from_json(value)


def test_a_game_starts_with_its_own_sharpness_while_that_is_active() -> None:
    softer = GameSharpness(GAME, "The Outer Worlds", Sharpness(strength=20))
    waiting = GameSharpness(OTHER, "Other", Sharpness(enabled=False), active=False)
    settings = Settings(sharpness=Sharpness(), game_sharpness=(softer, waiting))

    assert settings.sharpness_for(GAME) == Sharpness(strength=20)
    assert settings.sharpness_for(OTHER) == Sharpness()
    assert settings.sharpness_for(None) == Sharpness()
    saved = json.loads(json.dumps(settings.to_json()))
    again = Settings().updated({key: saved[key] for key in ("sharpness", "game_sharpness")})
    assert again == settings
    # After "restore everything" the games' profiles wait, and nothing is sharpened.
    restored = settings.restored()
    assert restored.sharpness is None
    assert [profile.active for profile in restored.game_sharpness] == [False, False]


def test_the_manifest_is_the_system_s_layer_without_its_condition() -> None:
    manifest = json.loads(manifest_text(SYSTEM))

    assert manifest["layer"]["name"] == LAYER
    assert manifest["layer"]["library_path"] == "/usr/$LIB/vkbasalt/libvkbasalt.so"
    assert "enable_environment" not in manifest["layer"]
    assert manifest["layer"]["disable_environment"] == {"DISABLE_VKBASALT": "1"}
    assert library_64(SYSTEM) == "/usr/lib64/vkbasalt/libvkbasalt.so"


@pytest.mark.parametrize(
    "text",
    ["[]", "{}", '{"layer": {"name": "VK_LAYER_other"}}', json.dumps({"layer": {"name": LAYER}})],
)
def test_another_manifest_is_not_taken_for_the_layer_s(text: str) -> None:
    with pytest.raises(ValueError):
        manifest_text(text)


def test_the_configuration_is_cas_alone_at_the_chosen_strength() -> None:
    text = config_text(Sharpness(strength=70))

    assert own_config(text)
    assert "effects = cas\n" in text
    assert "casSharpness = 0.70\n" in text
    # vkBasalt's own toggle key is Home.
    assert "toggleKey = F35\n" in text
    assert not own_config("effects = cas\ncasSharpness = 0.4\n")
    # Another program that merged its settings into ORIGAMI's file made the file its own.
    assert not own_config(text.replace("0.70", "0.50") + "ownEffect = /path/Effect.fx\n")
    assert not own_config(text + "ownEffect = /path/Effect.fx\n")


def test_launch_options_that_set_vkbasalt_are_told_from_those_that_only_name_it() -> None:
    assert sets_vkbasalt("DISABLE_VKBASALT=1 %command%")
    assert sets_vkbasalt("ENABLE_VKBASALT=1 VKBASALT_CONFIG_FILE=/home/user/game.conf %command%")
    assert sets_vkbasalt("    export DISABLE_VKBASALT=1\n    unset ENABLE_VKBASALT\n")
    # A wrapper that only clears the variables leaves vkBasalt to whoever loads it.
    assert not sets_vkbasalt(
        "unset ENABLE_GAMESCOPE_WSI DISABLE_VKBASALT ENABLE_VKBASALT DXVK_HDR\n"
    )
    assert not sets_vkbasalt("MANGOHUD=1 gamemoderun %command%")

    assert launch_programs("~/.wrapper %command% -novid") == ["~/.wrapper"]
    assert launch_programs("VAR=/opt/x /home/user/bin/run --fast %command%") == [
        "/home/user/bin/run"
    ]
    assert launch_programs("") == []


def test_the_state_of_a_running_game() -> None:
    on, stronger, off = Sharpness(), Sharpness(strength=70), Sharpness(enabled=False)

    def state(
        wanted: Sharpness | None, started: Sharpness | None, *, known: bool, loaded: bool
    ) -> GameState:
        return game_state(wanted=wanted, started=started, known=known, loaded=loaded)

    assert state(on, on, known=True, loaded=True) is GameState.WORKING
    assert state(stronger, on, known=True, loaded=True) is GameState.NEW_STRENGTH
    # On since before the start, and the layer is not there: the game does not draw with Vulkan.
    assert state(on, on, known=True, loaded=False) is GameState.MISSING
    assert state(on, None, known=True, loaded=False) is GameState.TURNING_ON
    assert state(off, on, known=True, loaded=True) is GameState.TURNING_OFF
    assert state(None, None, known=True, loaded=False) is GameState.OFF
    # A game whose start ORIGAMI did not see is told by the layer alone.
    assert state(on, None, known=False, loaded=True) is GameState.WORKING
    assert state(on, None, known=False, loaded=False) is GameState.TURNING_ON


def make_block(
    tmp_path: Path, user: FakeUser, owner: list[str | None] | None = None
) -> tuple[SharpnessBlock, Path]:
    """A block on a system that has vkBasalt, and the user's home."""
    root, home = tmp_path / "root", tmp_path / "root" / "home" / "user"
    home.mkdir(parents=True, exist_ok=True)
    manifest = root / SYSTEM_MANIFEST
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(SYSTEM, encoding="utf-8")
    library = root / "usr/lib64/vkbasalt/libvkbasalt.so"
    library.parent.mkdir(parents=True, exist_ok=True)
    library.touch()

    async def conflicts() -> Conflicts:
        return Conflicts(
            lighting=None,
            saturation=None,
            vibration=None,
            triggers=None,
            power=None,
            boost=None,
            fans=None,
            sound=None,
            sharpness=None if owner is None else owner[0],
        )

    journal = ChangeJournal(tmp_path / "changes.json")
    journal.load()
    context = Context(root, journal, conflicts)
    block = SharpnessBlock(context, home=home, companion="Frame Plugin", runner=user)
    return block, home


def in_journal(tmp_path: Path) -> bool:
    journal = ChangeJournal(tmp_path / "changes.json")
    journal.load()
    return journal.recorded(*JOURNAL)


def game_with_the_layer(tmp_path: Path, pid: int = 5000) -> Path:
    """A game's process that has the layer's library mapped."""
    maps = tmp_path / "root" / "proc" / str(pid) / "maps"
    maps.parent.mkdir(parents=True, exist_ok=True)
    maps.write_text(
        "7f00-7f10 r-xp 00000000 00:1f 42 /usr/lib64/vkbasalt/libvkbasalt.so\n", encoding="utf-8"
    )
    return maps


def test_the_system_is_supported_with_the_layer_and_a_home(tmp_path: Path) -> None:
    block, home = make_block(tmp_path, FakeUser())
    assert block.supported()

    (tmp_path / "root" / "usr/lib64/vkbasalt/libvkbasalt.so").unlink()
    assert not block.supported()
    (tmp_path / "root" / SYSTEM_MANIFEST).unlink()
    assert not block.supported()
    home.rmdir()
    assert not block.supported()


def test_the_files_are_there_from_a_game_s_launch_until_it_ends(tmp_path: Path) -> None:
    user = FakeUser()
    block, home = make_block(tmp_path, user)
    settings = Settings(sharpness=Sharpness(strength=70))

    async def scenario() -> None:
        # Switched on without a game: nothing is written yet.
        await block.follow(settings)
        assert not (home / MANIFEST).exists() and not (home / CONFIG).exists()
        assert user.calls == []
        assert (await block.state()).game is GameState.NO_GAME

        await block.game_starting(settings, GAME)
        assert json.loads((home / MANIFEST).read_text(encoding="utf-8"))["layer"]["name"] == LAYER
        assert "casSharpness = 0.70\n" in (home / CONFIG).read_text(encoding="utf-8")
        assert in_journal(tmp_path)
        # The configuration is whole before the layer can load.
        written = [call[-1] for call in user.calls if call[0] == "mv"]
        assert written == [str(home / CONFIG), str(home / MANIFEST)]

        await block.set_game(settings, GAME)
        game_with_the_layer(tmp_path)
        assert (await block.state()).game is GameState.WORKING

        await block.set_game(settings, None)
        assert not (home / MANIFEST).exists() and not (home / CONFIG).exists()
        assert not in_journal(tmp_path)
        block.stop()

    asyncio.run(scenario())
    owner = home.stat()
    assert set(user.users) == {(owner.st_uid, owner.st_gid)}


def test_a_change_while_a_game_runs_waits_for_its_next_start(tmp_path: Path) -> None:
    user = FakeUser()
    block, home = make_block(tmp_path, user)
    settings = Settings(sharpness=Sharpness())

    async def scenario() -> None:
        await block.game_starting(settings, GAME)
        await block.set_game(settings, GAME)
        maps = game_with_the_layer(tmp_path)

        stronger = Settings(sharpness=Sharpness(strength=70))
        await block.follow(stronger)
        assert "casSharpness = 0.70\n" in (home / CONFIG).read_text(encoding="utf-8")
        assert (await block.state()).game is GameState.NEW_STRENGTH

        # Switched off, the files go at once; the game keeps the layer it loaded.
        off = Settings(sharpness=Sharpness(enabled=False))
        await block.follow(off)
        assert not (home / MANIFEST).exists()
        assert (await block.state()).game is GameState.TURNING_OFF

        # Started again without the layer.
        await block.set_game(off, None)
        maps.unlink()
        await block.game_starting(off, GAME)
        await block.set_game(off, GAME)
        assert (await block.state()).game is GameState.OFF
        block.stop()

    asyncio.run(scenario())


def test_a_game_s_own_profile_decides_for_it(tmp_path: Path) -> None:
    user = FakeUser()
    block, home = make_block(tmp_path, user)
    without = GameSharpness(GAME, "The Outer Worlds", Sharpness(enabled=False))
    softer = GameSharpness(OTHER, "Other", Sharpness(strength=20))
    settings = Settings(sharpness=Sharpness(strength=70), game_sharpness=(without, softer))

    async def scenario() -> None:
        await block.game_starting(settings, GAME)
        assert not (home / MANIFEST).exists()
        await block.set_game(settings, GAME)
        assert (await block.state()).game is GameState.OFF
        await block.set_game(settings, None)

        await block.game_starting(settings, OTHER)
        assert "casSharpness = 0.20\n" in (home / CONFIG).read_text(encoding="utf-8")
        await block.set_game(settings, OTHER)
        # The layer is not in the game: it does not draw through Vulkan.
        assert (await block.state()).game is GameState.MISSING
        block.stop()

    asyncio.run(scenario())


def test_the_user_s_own_configuration_comes_back(tmp_path: Path) -> None:
    user = FakeUser()
    block, home = make_block(tmp_path, user)
    own = "effects = cas:fxaa\ncasSharpness = 0.9\n"
    (home / CONFIG).parent.mkdir(parents=True)
    (home / CONFIG).write_text(own, encoding="utf-8")
    settings = Settings(sharpness=Sharpness())

    async def scenario() -> None:
        await block.game_starting(settings, GAME)
        assert own_config((home / CONFIG).read_text(encoding="utf-8"))
        await block.set_game(settings, GAME)
        await block.set_game(settings, None)
        assert (home / CONFIG).read_text(encoding="utf-8") == own

        # A configuration somebody wrote over ORIGAMI's while the game ran stays.
        await block.game_starting(settings, GAME)
        (home / CONFIG).write_text("effects = smaa\n", encoding="utf-8")
        await block.set_game(settings, GAME)
        await block.set_game(settings, None)
        assert (home / CONFIG).read_text(encoding="utf-8") == "effects = smaa\n"
        assert not (home / MANIFEST).exists()
        block.stop()

    asyncio.run(scenario())


def test_files_left_by_a_run_that_did_not_end_go_at_the_next_start(tmp_path: Path) -> None:
    user = FakeUser()
    block, home = make_block(tmp_path, user)
    settings = Settings(sharpness=Sharpness())

    async def scenario() -> None:
        await block.game_starting(settings, GAME)
        block.stop()
        # ORIGAMI starts anew and no game runs.
        again, _ = make_block(tmp_path, user)
        await again.follow(settings)
        assert not (home / MANIFEST).exists() and not (home / CONFIG).exists()
        assert not in_journal(tmp_path)

    asyncio.run(scenario())


def test_a_launch_that_never_runs_is_given_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sharpness_block, "LAUNCH_SECONDS", 0.01)
    block, home = make_block(tmp_path, FakeUser())
    settings = Settings(sharpness=Sharpness())

    async def scenario() -> None:
        await block.game_starting(settings, GAME)
        assert (home / MANIFEST).exists()
        await asyncio.sleep(0.1)
        assert not (home / MANIFEST).exists()

    asyncio.run(scenario())


def test_a_game_whose_launch_was_not_seen_gets_the_files_for_its_next_start(
    tmp_path: Path,
) -> None:
    block, home = make_block(tmp_path, FakeUser())
    settings = Settings(sharpness=Sharpness())

    async def scenario() -> None:
        await block.set_game(settings, GAME)
        assert (home / MANIFEST).exists()
        assert (await block.state()).game is GameState.TURNING_ON
        game_with_the_layer(tmp_path)
        assert (await block.state()).game is GameState.WORKING

    asyncio.run(scenario())


def test_another_plugin_s_vkbasalt_is_left_alone(tmp_path: Path) -> None:
    owner: list[str | None] = ["Sharpness Plugin"]
    user = FakeUser()
    block, home = make_block(tmp_path, user, owner)
    settings = Settings(sharpness=Sharpness())

    async def scenario() -> None:
        await block.game_starting(settings, GAME)
        assert not (home / MANIFEST).exists()
        assert user.calls == []
        owner[0] = None
        await block.follow(settings)
        assert (home / MANIFEST).exists()
        block.stop()

    asyncio.run(scenario())


def test_a_failed_write_is_logged_and_the_next_launch_tries_again(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    user = FakeUser()
    block, home = make_block(tmp_path, user)
    settings = Settings(sharpness=Sharpness())

    async def scenario() -> None:
        user.failing = "chmod"
        await block.game_starting(settings, GAME)
        assert "Sharpness not set" in caplog.text
        # Nothing half-written stays, and nothing is listed as changed.
        assert list((home / CONFIG).parent.iterdir()) == []
        assert not (home / MANIFEST).exists()
        assert not in_journal(tmp_path)
        user.failing = None
        await block.game_starting(settings, GAME)
        assert (home / MANIFEST).exists()
        block.stop()

    asyncio.run(scenario())


def test_removing_origami_takes_the_files_away_without_waiting(tmp_path: Path) -> None:
    user = FakeUser()
    block, home = make_block(tmp_path, user)
    settings = Settings(sharpness=Sharpness())

    async def scenario() -> None:
        await block.game_starting(settings, GAME)
        await block.set_game(settings, GAME)
        block.stop()

    asyncio.run(scenario())
    block.give_back()

    assert not (home / MANIFEST).exists() and not (home / CONFIG).exists()
    assert not in_journal(tmp_path)


def test_the_layer_is_found_in_a_process_that_mapped_it(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "proc" / "100").mkdir(parents=True)
    (root / "proc" / "100" / "maps").write_text("7f00-7f10 r-xp /usr/lib64/libc.so.6\n")
    assert not layer_loaded(root)

    game_with_the_layer(tmp_path)
    assert layer_loaded(root)


def steam_process(tmp_path: Path, pid: int, *variables: str) -> None:
    """A process with this environment, as /proc shows it."""
    folder = tmp_path / "root" / "proc" / str(pid)
    folder.mkdir(parents=True)
    (folder / "environ").write_bytes("\0".join(variables).encode() + b"\0")


def test_a_game_whose_environment_sets_vkbasalt_says_so(tmp_path: Path) -> None:
    block, home = make_block(tmp_path, FakeUser())
    settings = Settings(sharpness=Sharpness())

    async def scenario() -> None:
        await block.game_starting(settings, GAME)
        await block.set_game(settings, GAME)
        assert (home / MANIFEST).exists()
        # Another program with the variable is no game of Steam's.
        steam_process(tmp_path, 100, "HOME=/home/user", "DISABLE_VKBASALT=1")
        steam_process(tmp_path, 200, f"SteamAppId={GAME}", "DISABLE_VKBASALT=10")
        assert (await block.state()).game is GameState.MISSING

        steam_process(tmp_path, 300, f"SteamAppId={GAME}", "DISABLE_VKBASALT=1", "ENABLE_OTHER=1")
        assert (await block.state()).game is GameState.MANAGED
        # Whatever ORIGAMI's own switch says, the sharpness in this game is not ORIGAMI's.
        off = Settings(sharpness=Sharpness(enabled=False))
        await block.follow(off)
        assert (await block.state()).game is GameState.MANAGED
        block.stop()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "variables",
    [("ENABLE_VKBASALT=1",), ("VKBASALT_CONFIG_FILE=/home/user/.config/tool/game.conf",)],
)
def test_the_files_go_once_the_game_s_environment_sets_vkbasalt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variables: tuple[str, ...]
) -> None:
    monkeypatch.setattr(sharpness_block, "WATCH_SECONDS", 0.01)
    block, home = make_block(tmp_path, FakeUser())
    settings = Settings(sharpness=Sharpness())

    async def scenario() -> None:
        # Launch options ORIGAMI could not read: the files are written as for any game.
        await block.game_starting(settings, GAME)
        await block.set_game(settings, GAME)
        assert (home / MANIFEST).exists()
        # A vkBasalt of the game's own is in it, with its own configuration.
        steam_process(tmp_path, 300, f"SteamAppId={GAME}", *variables)
        game_with_the_layer(tmp_path)
        await asyncio.sleep(0.1)
        assert not (home / MANIFEST).exists() and not (home / CONFIG).exists()
        assert not in_journal(tmp_path)
        assert (await block.state()).game is GameState.MANAGED
        # The next game is ORIGAMI's again.
        await block.set_game(settings, None)
        shutil.rmtree(tmp_path / "root" / "proc")
        await block.game_starting(settings, OTHER)
        assert (home / MANIFEST).exists()
        block.stop()

    asyncio.run(scenario())


def test_launch_options_that_set_vkbasalt_keep_it(tmp_path: Path) -> None:
    user = FakeUser()
    block, home = make_block(tmp_path, user)
    settings = Settings(sharpness=Sharpness())
    # A wrapper as a frame generation tool writes one: it builds the game's chain of layers itself.
    wrapper = home / ".local" / "bin" / LAUNCHER.wrapper
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text('#!/bin/bash\nexport DISABLE_VKBASALT=1\nexec "$@"\n', encoding="utf-8")
    # One that only clears the variables, as another such tool writes.
    clearing = home / ".clear"
    clearing.write_text(
        '#!/bin/sh\nunset DISABLE_VKBASALT ENABLE_VKBASALT\nexec "$@"\n', encoding="utf-8"
    )

    async def scenario() -> None:
        for options in (
            f"{wrapper} %command%",
            f"~/.local/bin/{LAUNCHER.wrapper} %command%",
            "DISABLE_VKBASALT=1 %command%",
        ):
            await block.game_starting(settings, GAME, options)
            assert not (home / MANIFEST).exists() and not (home / CONFIG).exists(), options
            assert user.calls == []
            await block.set_game(settings, GAME)
            state = await block.state()
            assert state.game is GameState.MANAGED
            # The plugin is named where the launch options run its wrapper.
            named = LAUNCHER.wrapper in options
            assert state.owner == (LAUNCHER.plugin if named else None)
            assert state.sharpening == (LAUNCHER.sharpening if named else None)
            assert state.companion == "Frame Plugin"
            await block.set_game(settings, None)

        for options in ("~/.clear %command%", "", "/no/such/file %command%", None):
            await block.game_starting(settings, GAME, options)
            assert (home / MANIFEST).exists(), options
            await block.set_game(settings, GAME)
            await block.set_game(settings, None)
        block.stop()

    asyncio.run(scenario())


def test_a_configuration_another_program_merged_into_stays_as_it_left_it(tmp_path: Path) -> None:
    block, home = make_block(tmp_path, FakeUser())
    settings = Settings(sharpness=Sharpness())

    async def scenario() -> None:
        await block.game_starting(settings, GAME)
        own = (home / CONFIG).read_text(encoding="utf-8")
        merged = own.replace("0.40", "0.50") + "ownEffect = /path/Effect.fx\n"
        (home / CONFIG).write_text(merged, encoding="utf-8")
        await block.set_game(settings, GAME)
        await block.set_game(settings, None)
        assert (home / CONFIG).read_text(encoding="utf-8") == merged
        assert not (home / MANIFEST).exists()

        # It is the user's own file from then on: kept while the next game runs, and put back.
        await block.game_starting(settings, OTHER)
        assert own_config((home / CONFIG).read_text(encoding="utf-8"))
        await block.set_game(settings, OTHER)
        await block.set_game(settings, None)
        assert (home / CONFIG).read_text(encoding="utf-8") == merged
        block.stop()

    asyncio.run(scenario())


def test_a_running_game_with_its_own_vkbasalt_is_left_alone_from_the_first_look(
    tmp_path: Path,
) -> None:
    user = FakeUser()
    block, home = make_block(tmp_path, user)
    settings = Settings(sharpness=Sharpness())
    theirs = "effects = cas:fxaa"
    (home / CONFIG).parent.mkdir(parents=True)
    (home / CONFIG).write_text(theirs, encoding="utf-8")
    steam_process(tmp_path, 300, f"SteamAppId={GAME}", "VKBASALT_CONFIG_FILE=/x.conf")

    async def scenario() -> None:
        # ORIGAMI starts while the game runs: it did not see the launch.
        await block.follow(settings)
        await block.set_game(settings, GAME)
        assert user.calls == []
        assert (home / CONFIG).read_text(encoding="utf-8") == theirs
        assert (await block.state()).game is GameState.MANAGED
        block.stop()

    asyncio.run(scenario())
