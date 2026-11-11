# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Sound tile: ORIGAMI's filter in front of the speakers, and the clock fix after sleep."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from origami import clock
from origami.blocks import Context
from origami.fsutil import atomic_write_text
from origami.jsonio import JsonValue
from origami.proc import CommandError, run, run_blocking, start_detached
from origami.settings import Settings
from origami.sound import (
    SPEAKER_ZONES,
    Sound,
    Speakers,
    chain_config,
    controls,
    filter_node,
    find_speakers,
    foreign_filter,
    parse_dump,
    set_param_props,
)
from origami.tasks import BackgroundTask

log = logging.getLogger(__name__)

UNIT = "origami-sound"
"""The session user's transient service that runs the filter's pipewire process."""
UNIT_NOT_LOADED = 5
"""systemctl's exit code for a unit that does not exist: a filter that is not running."""
JOURNAL = ("sound", "filter")
"""The filter in the journal of changes, while ORIGAMI processes the speakers."""
CONFIG = "origami-sound.conf"
"""The filter's configuration, in the session user's runtime directory."""
POLL_SECONDS = 2.0
"""How often ORIGAMI looks whether the speakers play and the filter runs, while it is on."""
TIMEOUT_SECONDS = 10
GIVE_BACK_SECONDS = 3
"""Decky ends a plugin 5 s into its removal, so the last stop waits less than that."""
START_GRACE_SECONDS = 8.0
"""How long a started filter may take to show its node: under 2 s on a console at rest."""
STEADY_SECONDS = 60.0
"""A filter that ran this long and then went is started again at once, as after a PipeWire
restart; one that went sooner did not stay up."""
RETRY_SECONDS = (4.0, 15.0, 60.0, 300.0)
"""The waits before starting again a filter that did not stay up: the last one from then on."""
RUN_USER = Path("run/user")
LV2_DIR = Path("bin/lv2")
"""The LSP plugins the filter runs, in ORIGAMI's folder."""


class Runner(Protocol):
    """origami.proc.run, as the block calls it."""

    def __call__(
        self, *args: str, user: tuple[int, int] | None = None, env: Mapping[str, str] | None = None
    ) -> Awaitable[str]: ...


@dataclass(frozen=True, slots=True)
class SoundState:
    """What the Sound screen shows besides the settings."""

    speakers: bool
    """There is a speaker sink: PipeWire runs and the console has its speakers."""
    headphones: bool
    """Headphones play on the speakers' sink, so the filter waits for the speakers."""
    running: bool
    """The filter runs in front of the speakers now."""
    owner: str | None
    """Another program whose filter processes the speakers now, found in PipeWire; None when
    none. A Decky plugin known to own the sound is among the conflicts as well."""
    failed: bool
    """The filter did not stay up after its last start, and ORIGAMI waits to try again."""
    clock_fix: bool
    """The crackle after sleep happens here, so the screen offers its fix. Where it does not
    (the hardware clock went to UTC, or the zone is UTC+0 for the winter) a fix switched on
    earlier does nothing, and the screen does not show it."""


class SoundBlock:
    """Runs the filter while the sound is on, the speakers play and no plugin processes them.

    The filter is a pipewire process of the session user, in a transient user service, so it lives
    in the user's PipeWire session and goes when that does. ORIGAMI looks every POLL_SECONDS while
    the sound is on: headphones on the speakers' sink stop the filter, and a PipeWire restart that
    took it away starts it again. A changed setting goes into the running filter through set-param.

    The journal of changes holds the filter from its first start until the sound is switched
    off or another plugin takes it: headphones only make it wait.

    A filter that does not stay up (PipeWire cannot load it) is started again after longer and
    longer waits, not every time ORIGAMI looks. A command that fails is logged and the watching
    goes on: the next look puts things right.
    """

    def __init__(
        self,
        context: Context,
        *,
        lv2_dir: Path,
        board: Callable[[], str | None],
        runner: Runner = run,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._context = context
        self._lv2_dir = lv2_dir
        self._board = board
        self._run = runner
        self._now = now
        self._sound: Sound | None = None
        self._game: int | None = None
        """The game Steam runs now, whose own sound applies while it has an active profile."""
        self._own: int | None = None
        """The game whose profile is the sound in use; None while the general one is."""
        self._applied: dict[str, float] | None = None
        """The controls the running filter has; None until ORIGAMI started it in this run."""
        self._sink: str | None = None
        self._started_at = 0.0
        self._seen = False
        """The filter ORIGAMI started has shown its node."""
        self._failures = 0
        """Starts in a row after which the filter did not stay up."""
        self._retry_at = 0.0
        self._clean = False
        """ORIGAMI has seen that no filter of its own runs: switched off, nothing is to stop."""
        self._problem: str | None = None
        """The last failure logged, so one that repeats every look is logged once."""
        self._lock = asyncio.Lock()
        self._watch = BackgroundTask("origami-sound", self._keep)
        self._clock = BackgroundTask("origami-clock", lambda: clock.step_when_off(self._run))

    def supported(self) -> bool:
        board = self._board()
        return board is not None and board in SPEAKER_ZONES

    async def follow(self, settings: Settings) -> None:
        """Start, change or stop the filter for these settings, and keep watching while it is on."""
        supported = self.supported()
        self._sound = settings.sound_for(self._game) if supported else None
        # Told once each time the sound in use changes hands, by a game starting or by its switch.
        own = self._game if supported and self._sound is not settings.sound else None
        if own != self._own:
            log.info("Sound: %s", "general again" if own is None else f"the profile of game {own}")
            self._own = own
        on = self._sound is not None and self._sound.enabled
        await self._look()
        await self._watch.run_while(on=on)

    async def set_game(self, settings: Settings, app_id: int | None) -> None:
        """Steam runs this game now, or none: the sound follows the game's own profile, if any."""
        if app_id == self._game:
            return
        self._game = app_id
        await self.follow(settings)

    async def state(self) -> SoundState:
        root = self._context.root
        offered = await asyncio.to_thread(clock.crackles_after_sleep, root)
        objects = await self._dump()
        speakers = find_speakers(objects) if objects is not None else None
        running = objects is not None and filter_node(objects) is not None
        return SoundState(
            speakers=speakers is not None,
            headphones=speakers is not None and not speakers.playing,
            owner=None if objects is None else _foreign(objects, speakers),
            running=running,
            failed=not running and self._failures > 0,
            clock_fix=offered,
        )

    async def watch_clock(self, settings: Settings) -> None:
        """Watch chrony a while and step the clock as soon as it is off.

        Called as the console wakes and as the fix is switched on.
        """
        if settings.clock_fix and await asyncio.to_thread(
            clock.crackles_after_sleep, self._context.root
        ):
            # A new call starts the wait for chrony's measurement over.
            self._clock.cancel()
            self._clock.start()

    def stop(self) -> None:
        """Stop watching, and the filter with it, without waiting: Decky is unloading ORIGAMI."""
        self._watch.cancel()
        self._clock.cancel()
        user = self._user()
        if user is None:
            return
        try:
            start_detached("systemctl", "--user", "stop", UNIT, user=user, env=_session(user))
        except CommandError as error:
            log.warning("Sound filter not stopped: %s", error)

    def give_back(self) -> None:
        """Stop the filter for good, waiting a few seconds at most, and remove its configuration.

        Decky removes ORIGAMI.
        """
        user = self._user()
        if user is None:
            # Without the user's session there is no filter in it either.
            self._context.journal.forget(*JOURNAL)
            return
        stopped = True
        try:
            run_blocking(
                "systemctl",
                "--user",
                "stop",
                UNIT,
                timeout=GIVE_BACK_SECONDS,
                user=user,
                env=_session(user),
            )
        except TimeoutError as error:
            stopped = False
            log.warning("Sound filter not stopped: %s", error)
        except CommandError as error:
            if error.returncode != UNIT_NOT_LOADED:
                stopped = False
                log.warning("Sound filter not stopped: %s", error)
        if stopped:
            # A filter that could not be stopped stays in the journal, for the screen to list.
            self._context.journal.forget(*JOURNAL)
        try:
            (self._context.root / RUN_USER / str(user[0]) / CONFIG).unlink(missing_ok=True)
        except OSError as error:
            log.warning("Sound filter configuration not removed: %s", error)

    async def _keep(self) -> None:
        while True:
            await asyncio.sleep(POLL_SECONDS)
            await self._look()

    async def _look(self) -> None:
        """One look at the filter; a failed command is logged, once while it repeats."""
        try:
            await self._sync()
        except (CommandError, TimeoutError, OSError) as error:
            problem = str(error) or type(error).__name__
            if problem != self._problem:
                log.warning("Sound filter not set: %s", problem)
            self._problem = problem
        else:
            self._problem = None

    async def _sync(self) -> None:
        async with self._lock:
            sound = self._sound
            wanted = sound is not None and sound.enabled
            if not wanted and self._clean:
                return
            owner = (await self._context.conflicts()).sound
            objects = await self._dump()
            if objects is None:
                # The session's PipeWire does not answer: nothing to go by, except switched off.
                if not wanted and self._applied is not None:
                    await self._stop()
                return
            speakers = find_speakers(objects)
            node = filter_node(objects)
            # A plugin known to own the sound, or whatever else stands in front of the speakers.
            owner = owner or _foreign(objects, speakers)
            if (
                sound is None
                or not sound.enabled
                or owner is not None
                or speakers is None
                or not speakers.playing
            ):
                # A filter just started shows no node yet and is stopped all the same.
                stopped = True
                if node is not None or self._applied is not None:
                    stopped = await self._stop()
                    if stopped and wanted and owner is not None:
                        log.info("Sound is left to %s, which processes the speakers", owner)
                if stopped and (not wanted or owner is not None):
                    # Headphones and missing speakers keep the entry: the filter comes back.
                    await asyncio.to_thread(self._context.journal.forget, *JOURNAL)
                self._clean = stopped
                # Switched on again, the filter starts at once.
                self._failures = 0
                self._retry_at = 0.0
                return
            applied = self._applied
            if node is None:
                await self._start_again(sound, speakers)
                return
            if applied is None or speakers.sink != self._sink:
                await self._start(sound, speakers)
                return
            if not self._seen:
                self._seen = True
                log.info("Sound filter started in front of %s: %s", speakers.sink, sound.to_json())
            values = controls(sound)
            changed = {name: value for name, value in values.items() if applied.get(name) != value}
            if changed:
                await self._user_run(
                    "pw-cli", "set-param", str(node), "Props", set_param_props(changed)
                )
                self._applied = values

    async def _start_again(self, sound: Sound, speakers: Speakers) -> None:
        """No node: start the filter, unless it is still coming up or a failed start waits."""
        now = self._now()
        if self._applied is not None:
            age = now - self._started_at
            if not self._seen and age < START_GRACE_SECONDS:
                return
            if self._seen and age >= STEADY_SECONDS:
                self._failures = 0
                self._retry_at = now
            else:
                wait = RETRY_SECONDS[min(self._failures, len(RETRY_SECONDS) - 1)]
                self._failures += 1
                self._retry_at = now + wait
                log.warning(
                    "Sound filter did not stay up (%d in a row); the next try is in %d s",
                    self._failures,
                    wait,
                )
            self._applied = None
            self._seen = False
        if now >= self._retry_at:
            await self._start(sound, speakers)

    async def _start(self, sound: Sound, speakers: Speakers) -> None:
        user = self._user()
        board = self._board()
        if user is None or board is None:
            return
        config = self._context.root / RUN_USER / str(user[0]) / CONFIG
        text = chain_config(SPEAKER_ZONES[board], speakers.sink, sound)
        await asyncio.to_thread(atomic_write_text, config, text)
        await self._stop()
        # The speakers played as the system has them before ORIGAMI, not a value.
        await asyncio.to_thread(self._context.journal.record, *JOURNAL, None)
        await self._user_run(
            "systemd-run",
            "--user",
            f"--unit={UNIT}",
            "--collect",
            "--quiet",
            f"--setenv=LV2_PATH={self._lv2_dir}",
            "/usr/bin/pipewire",
            "-c",
            str(config),
        )
        self._applied = controls(sound)
        self._sink = speakers.sink
        self._started_at = self._now()
        self._seen = False
        self._clean = False

    async def _stop(self) -> bool:
        """Stop the filter's service; False when it could not be stopped."""
        try:
            await self._user_run("systemctl", "--user", "stop", UNIT)
        except CommandError as error:
            if error.returncode != UNIT_NOT_LOADED:
                log.warning("Sound filter not stopped: %s", error)
                return False
        except TimeoutError:
            log.warning("Sound filter not stopped: systemctl did not answer")
            return False
        if self._seen:
            log.info("Sound filter stopped")
        self._applied = None
        self._seen = False
        return True

    async def _dump(self) -> list[JsonValue] | None:
        """pw-dump's objects, or None while the session's PipeWire does not answer."""
        try:
            return parse_dump(await self._user_run("pw-dump"))
        except (CommandError, TimeoutError, ValueError) as error:
            log.debug("No PipeWire objects: %s", error)
            return None

    async def _user_run(self, *args: str) -> str:
        user = self._user()
        if user is None:
            raise CommandError("No session user runs PipeWire")
        async with asyncio.timeout(TIMEOUT_SECONDS):
            return await self._run(*args, user=user, env=_session(user))

    def _user(self) -> tuple[int, int] | None:
        """The session user, by the owner of their PipeWire socket."""
        for socket in sorted((self._context.root / RUN_USER).glob("*/pipewire-0")):
            try:
                owner = socket.stat()
            except OSError:
                continue
            if owner.st_uid != 0:
                return owner.st_uid, owner.st_gid
        return None


def _foreign(objects: list[JsonValue], speakers: Speakers | None) -> str | None:
    return foreign_filter(objects, None if speakers is None else speakers.sink)


def _session(user: tuple[int, int]) -> dict[str, str]:
    """What systemctl --user, systemd-run --user and the PipeWire tools need to find the session."""
    runtime = f"/run/user/{user[0]}"
    return {"XDG_RUNTIME_DIR": runtime, "DBUS_SESSION_BUS_ADDRESS": f"unix:path={runtime}/bus"}
