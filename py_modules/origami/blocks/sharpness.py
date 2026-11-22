# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Service tile's sharpness: vkBasalt's layer in the games, while one starts and runs."""

import asyncio
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from origami.blocks import Context
from origami.decky_plugins import Launcher, launcher_in
from origami.gameprocs import game_processes
from origami.proc import CommandError, run_blocking
from origami.settings import Settings
from origami.sharpness import (
    BUILDS,
    LIBRARY,
    GameState,
    Sharpness,
    config_text,
    game_state,
    launch_programs,
    manifest_text,
    own_config,
    sets_vkbasalt,
)
from origami.tasks import BackgroundTask

log = logging.getLogger(__name__)

VKBASALT_DIR = Path("bin/vkbasalt")
"""ORIGAMI's own builds of vkBasalt in the plugin's folder (scripts/build_vkbasalt.sh)."""
MANIFESTS = {
    "64": Path(".local/share/vulkan/implicit_layer.d/origami_sharpness.json"),
    "32": Path(".local/share/vulkan/implicit_layer.d/origami_sharpness32.json"),
}
"""ORIGAMI's manifests of the layer in the user's home, one for each kind of game: the loader
looks there before /usr."""
MANIFEST = MANIFESTS["64"]
"""The manifest most games take: nearly all of them are 64-bit."""
CONFIG = Path(".config/vkBasalt/vkBasalt.conf")
"""vkBasalt's configuration in the user's home. The one in /etc is not seen inside Steam's
container, where the games run."""
OWN_VARIABLES = (b"DISABLE_VKBASALT=1", b"ENABLE_VKBASALT=1")
OWN_CONFIG_VARIABLE = b"VKBASALT_CONFIG_FILE="
"""vkBasalt's variables in a game's environment: its launch options set vkBasalt themselves."""
MAX_SCRIPT_BYTES = 1_000_000
"""A launch wrapper is a script of some kilobytes; a bigger file is a program and is not read."""
WATCH_SECONDS = 2.0
WATCH_LOOKS = 45
"""How often and how many times ORIGAMI looks, after a launch, whether the game's environment
sets vkBasalt itself: launch options ORIGAMI could not read beforehand."""
JOURNAL = ("sharpness", "layer")
"""The layer in the journal of changes while its files are there; the original is the user's own
vkBasalt configuration that ORIGAMI's took the place of, None when there was none."""
LAUNCH_SECONDS = 180.0
"""How long a game may take from its launch to running; after that the launch has failed."""
TIMEOUT_SECONDS = 5.0
GIVE_BACK_SECONDS = 1.0
"""Decky ends a plugin 5 s into its removal, and the sound's filter may take 3 s of them."""
MAX_CONFIG_BYTES = 65536
"""As much of the user's own configuration as ORIGAMI keeps to put back: far over any real one."""


class Runner(Protocol):
    """origami.proc.run_blocking, as the block calls it."""

    def __call__(
        self,
        *args: str,
        timeout: float,
        user: tuple[int, int] | None = None,
        feed: str | None = None,
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class SharpnessState:
    """What the Service screen shows of the sharpness besides the settings."""

    game: GameState
    owner: str | None = None
    """The plugin whose launch wrapper keeps vkBasalt in the running game; None where the launch
    options do it by themselves, and in a game whose sharpness is ORIGAMI's."""
    sharpening: str | None = None
    """Where that plugin has a sharpening of its own (decky_plugins.Launcher.sharpening)."""
    companion: str | None = None
    """A frame generation plugin in whose games ORIGAMI's sharpness works, told beside the owner
    as the way to have both."""


class SharpnessBlock:
    """Keeps the layer's manifest and configuration in the user's home while a game needs them.

    The files are there from a game's launch until it ends, when the sharpness is on for that
    game, and at no other time: whatever starts without a game (the system's overlay menu, Steam's
    shader processing) finds no layer. A game's own profile decides for it, else the general
    setting. A change made while a game runs is written at once, but the game takes it only when
    it starts next.

    ORIGAMI runs as root in the user's home, so the files are written and removed by programs run
    as the user: they can do there only what the user can, whatever links the home holds.

    `layer` is the folder of ORIGAMI's own builds of vkBasalt, which the manifests point at.
    """

    def __init__(
        self,
        context: Context,
        *,
        home: Path,
        layer: Path,
        companion: str | None = None,
        runner: Runner | None = None,
    ) -> None:
        self._context = context
        self._home = home
        self._layer = layer
        self._companion = companion
        self._run: Runner = run_blocking if runner is None else runner
        self._settings = Settings()
        self._game: int | None = None
        """The game Steam runs now."""
        self._starting: int | None = None
        """The game Steam launches now, until it runs or its launch is given up."""
        self._on_disk: Sharpness | None = None
        """The sharpness the files hold; None while they are not there."""
        self._started: Sharpness | None = None
        """What the running game found as it started, where ORIGAMI saw its launch."""
        self._known = False
        self._managed: int | None = None
        """The game whose launch options set vkBasalt themselves: ORIGAMI leaves it to them."""
        self._launcher: Launcher | None = None
        """The plugin whose wrapper those launch options run, where ORIGAMI knows it."""
        self._lock = asyncio.Lock()
        self._files = threading.Lock()
        self._launch = BackgroundTask("origami-sharpness-launch", self._give_launch_up)
        self._watch = BackgroundTask("origami-sharpness-watch", self._watch_environment)

    def supported(self) -> bool:
        """ORIGAMI has both builds of the layer, and the user has a home."""
        builds = all((self._layer / folder / LIBRARY).is_file() for folder in BUILDS.values())
        return builds and self._home.is_dir()

    async def follow(self, settings: Settings) -> None:
        """Write or remove the files for these settings and the game that starts or runs."""
        self._settings = settings
        await self._sync()

    async def game_starting(
        self, settings: Settings, app_id: int, launch_options: str | None = None
    ) -> None:
        """Steam launches this game: its files are there before it creates its Vulkan instance.

        Launch options that set vkBasalt themselves keep it: two writers of one configuration
        would spoil each other's, so ORIGAMI writes nothing for such a game.
        """
        self._settings = settings
        managed = await asyncio.to_thread(self._managed_by_launch, launch_options)
        self._managed = app_id if managed else None
        self._launcher = launcher_in(launch_options) if managed and launch_options else None
        if managed:
            log.info("Sharpness is left to the launch options of game %d", app_id)
        self._launch.cancel()
        # Steam may have told of the game already: then there is no launch left to wait for.
        if app_id != self._game:
            self._starting = app_id
            self._launch.start()
        await self._sync()
        self._watch_again()

    async def set_game(self, settings: Settings, app_id: int | None) -> None:
        """Steam runs this game now, or none."""
        self._settings = settings
        if app_id == self._game:
            return
        self._game = app_id
        if app_id is None:
            self._started, self._known = None, False
            # A game launched meanwhile keeps what its launch told of it.
            if self._starting is None:
                self._managed = None
                self._launcher = None
                self._watch.cancel()
        else:
            # A game whose launch ORIGAMI did not see found files ORIGAMI cannot tell.
            self._known = self._starting == app_id
            self._started = self._on_disk if self._known else None
            self._starting = None
            self._launch.cancel()
            # A game already running when ORIGAMI learns of it shows in its environment whose
            # vkBasalt it has: nothing is written into a configuration another program reads.
            if not self._known and await asyncio.to_thread(managed_by_game, self._context.root):
                self._managed = app_id
        await self._sync()
        if app_id is not None:
            self._watch_again()

    async def state(self) -> SharpnessState:
        """How the sharpness stands in the running game, for the screen."""
        game = self._game
        if game is None:
            return SharpnessState(GameState.NO_GAME)
        root = self._context.root
        if game == self._managed or await asyncio.to_thread(managed_by_game, root):
            # The layer in such a game, if any, is not ORIGAMI's to tell of or to set.
            self._managed = game
            launcher = self._launcher
            return SharpnessState(
                GameState.MANAGED,
                owner=None if launcher is None else launcher.plugin,
                sharpening=None if launcher is None else launcher.sharpening,
                companion=self._companion,
            )
        loaded = await asyncio.to_thread(layer_loaded, root)
        wanted = await self._wanted(game)
        return SharpnessState(
            game_state(wanted=wanted, started=self._started, known=self._known, loaded=loaded)
        )

    def stop(self) -> None:
        """Decky is unloading ORIGAMI: the files go, as nothing would take them away afterwards.

        The game that runs has the layer loaded already. Left behind, the files would load it into
        whatever starts while ORIGAMI is switched off, or after the system restarts.
        """
        self.give_back()

    def give_back(self) -> None:
        """Remove the files and put the user's own configuration back, without waiting long."""
        self._launch.cancel()
        self._watch.cancel()
        try:
            with self._files:
                self._take_away(GIVE_BACK_SECONDS)
        except (CommandError, TimeoutError, OSError) as error:
            log.warning("Sharpness not taken away: %s", error)

    async def _give_launch_up(self) -> None:
        await asyncio.sleep(LAUNCH_SECONDS)
        self._starting = None
        await self._sync()

    def _watch_again(self) -> None:
        self._watch.cancel()
        self._watch.start()

    async def _watch_environment(self) -> None:
        """Take the files away once the game's own environment turns out to set vkBasalt."""
        for _ in range(WATCH_LOOKS):
            await asyncio.sleep(WATCH_SECONDS)
            game = self._starting if self._starting is not None else self._game
            if game is None or game == self._managed or self._on_disk is None:
                return
            if await asyncio.to_thread(managed_by_game, self._context.root):
                self._managed = game
                log.info("Sharpness is left to game %d, whose environment sets vkBasalt", game)
                await self._sync()
                return

    def _managed_by_launch(self, options: str | None) -> bool:
        """Whether the launch options, or a script they run, set vkBasalt's variables."""
        if options is None:
            return False
        # A known wrapper builds the chain of layers itself, however the options spell its path.
        if sets_vkbasalt(options) or launcher_in(options) is not None:
            return True
        for program in launch_programs(options):
            script = self._home / program[2:] if program.startswith("~/") else Path(program)
            try:
                # What the system makes up as it is read (/proc) has no size, and is no script.
                if not script.is_file() or not 0 < script.stat().st_size <= MAX_SCRIPT_BYTES:
                    continue
                with script.open("rb") as file:
                    text = file.read(MAX_SCRIPT_BYTES).decode(errors="replace")
            except OSError:
                continue
            if sets_vkbasalt(text):
                return True
        return False

    async def _wanted(self, game: int) -> Sharpness | None:
        """The sharpness this game is to start with; None when it is to start without the layer."""
        if game == self._managed:
            return None
        sharpness = self._settings.sharpness_for(game)
        if sharpness is None or not sharpness.enabled:
            return None
        owner = (await self._context.conflicts()).sharpness
        return None if owner is not None else sharpness

    async def _sync(self) -> None:
        async with self._lock:
            game = self._starting if self._starting is not None else self._game
            wanted = None if game is None else await self._wanted(game)
            # The first write for a game that runs already: its environment shows whether another
            # program reads the configuration ORIGAMI would write.
            first = wanted is not None and self._on_disk is None and game == self._game
            if first and await asyncio.to_thread(managed_by_game, self._context.root):
                self._managed, wanted = game, None
            try:
                await asyncio.to_thread(self._set, wanted)
            except (CommandError, TimeoutError, OSError, ValueError) as error:
                log.warning(
                    "Sharpness not %s: %s", "taken away" if wanted is None else "set", error
                )

    def _set(self, wanted: Sharpness | None) -> None:
        # One at a time, also when the task that asked before was cancelled while its thread ran.
        with self._files:
            if wanted is None:
                self._take_away(TIMEOUT_SECONDS)
            elif wanted != self._on_disk:
                try:
                    self._put(wanted)
                except CommandError, TimeoutError, OSError:
                    # Half of the files would load the layer with another configuration, or none.
                    self._take_away(TIMEOUT_SECONDS)
                    raise

    def _put(self, sharpness: Sharpness) -> None:
        user = self._user()
        journal = self._context.journal
        if not journal.recorded(*JOURNAL):
            journal.record(*JOURNAL, self._users_config(user))
        # The configuration first: the layer never loads with another one.
        self._write(self._home / CONFIG, config_text(sharpness), user, TIMEOUT_SECONDS)
        for bits, manifest in MANIFESTS.items():
            text = manifest_text(self._layer / BUILDS[bits] / LIBRARY, bits)
            self._write(self._home / manifest, text, user, TIMEOUT_SECONDS)
        self._on_disk = sharpness
        log.info("Sharpness %d%% for the games that start now", sharpness.strength)

    def _take_away(self, timeout: float) -> None:
        journal = self._context.journal
        config = self._home / CONFIG
        manifests = [str(self._home / manifest) for manifest in MANIFESTS.values()]
        if not journal.recorded(*JOURNAL) and not any(map(os.path.lexists, manifests)):
            self._on_disk = None
            return
        user = self._user()
        self._run("rm", "-f", *manifests, timeout=timeout, user=user)
        # Without the manifests the next game needs the files written again, whatever fails below.
        self._on_disk = None
        # A configuration written over ORIGAMI's meanwhile is somebody's own and stays.
        if os.path.lexists(config) and own_config(self._read(config, user, timeout)):
            original = journal.original(*JOURNAL)
            if isinstance(original, str):
                self._write(config, original, user, timeout)
            else:
                self._run("rm", "-f", str(config), timeout=timeout, user=user)
        journal.forget(*JOURNAL)
        self._on_disk = None
        log.info("Sharpness taken away: no game needs it now")

    def _users_config(self, user: tuple[int, int]) -> str | None:
        """The vkBasalt configuration the user has of their own, to put back afterwards."""
        config = self._home / CONFIG
        if not os.path.lexists(config):
            return None
        text = self._read(config, user, TIMEOUT_SECONDS)
        # ORIGAMI's own file, left by a run that ended without taking it away.
        return None if own_config(text) else text

    def _read(self, path: Path, user: tuple[int, int], timeout: float) -> str:
        return self._run("head", "-c", str(MAX_CONFIG_BYTES), str(path), timeout=timeout, user=user)

    def _write(self, path: Path, text: str, user: tuple[int, int], timeout: float) -> None:
        """Put a file into the user's home as theirs, whole or not at all."""
        fresh = path.with_name(f".{path.name}.tmp")
        self._run("mkdir", "-p", str(path.parent), timeout=timeout, user=user)
        # dd reads the input it was started with: a program that opens /dev/stdin anew is refused,
        # as the pipe is root's.
        try:
            self._run("dd", f"of={fresh}", "status=none", timeout=timeout, user=user, feed=text)
            self._run("chmod", "644", str(fresh), timeout=timeout, user=user)
            self._run("mv", "-f", str(fresh), str(path), timeout=timeout, user=user)
        except CommandError, TimeoutError:
            self._run("rm", "-f", str(fresh), timeout=timeout, user=user)
            raise

    def _user(self) -> tuple[int, int]:
        """The user, by the owner of their home; OSError when the home is not there."""
        owner = self._home.stat()
        return owner.st_uid, owner.st_gid


def layer_loaded(root: Path) -> bool:
    """Whether a game's process has vkBasalt's library mapped: the game loaded the layer.

    Only the games' processes count: while the files are there, anything else that starts with
    Vulkan loads the layer too.
    """
    for process, _ in game_processes(root):
        try:
            if LIBRARY in (process / "maps").read_text(encoding="utf-8", errors="replace"):
                return True
        except OSError:
            # The process ended meanwhile.
            continue
    return False


def managed_by_game(root: Path) -> bool:
    """Whether a game Steam started runs with vkBasalt's variables set in its environment.

    Launch options do that, and so does a wrapper in them that builds the game's chain of Vulkan
    layers itself: it switches vkBasalt off, or loads one of its own with its own configuration.
    """
    return any(
        item in OWN_VARIABLES or item.startswith(OWN_CONFIG_VARIABLE)
        for _, variables in game_processes(root)
        for item in variables
    )
