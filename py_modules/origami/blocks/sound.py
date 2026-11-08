# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Sound tile: ORIGAMI's filter in front of the speakers, and the clock fix after sleep."""

import asyncio
import logging
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
    parse_dump,
    set_param_props,
)
from origami.tasks import BackgroundTask

log = logging.getLogger(__name__)

UNIT = "origami-sound"
"""The session user's transient service that runs the filter's pipewire process."""
UNIT_NOT_LOADED = 5
"""systemctl's exit code for a unit that does not exist: a filter that is not running."""
CONFIG = "origami-sound.conf"
"""The filter's configuration, in the session user's runtime directory."""
POLL_SECONDS = 2.0
"""How often ORIGAMI looks whether the speakers play and the filter runs, while it is on."""
TIMEOUT_SECONDS = 10
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
    clock_fix: bool
    """The crackle after sleep happens here, so the screen offers its fix."""


class SoundBlock:
    """Runs the filter while the sound is on, the speakers play and no plugin processes them.

    The filter is a pipewire process of the session user, in a transient user service, so it lives
    in the user's PipeWire session and goes when that does. ORIGAMI looks every POLL_SECONDS while
    the sound is on: headphones on the speakers' sink stop the filter, and a PipeWire restart that
    took it away starts it again. A changed setting goes into the running filter through set-param.
    """

    def __init__(
        self,
        context: Context,
        *,
        lv2_dir: Path,
        board: Callable[[], str | None],
        runner: Runner = run,
    ) -> None:
        self._context = context
        self._lv2_dir = lv2_dir
        self._board = board
        self._run = runner
        self._sound: Sound | None = None
        self._applied: dict[str, float] | None = None
        """The controls the running filter has; None until ORIGAMI started it in this run."""
        self._sink: str | None = None
        self._lock = asyncio.Lock()
        self._watch = BackgroundTask("origami-sound", self._keep)

    def supported(self) -> bool:
        board = self._board()
        return board is not None and board in SPEAKER_ZONES

    async def follow(self, settings: Settings) -> None:
        """Start, change or stop the filter for these settings, and keep watching while it is on."""
        self._sound = settings.sound if self.supported() else None
        on = self._sound is not None and self._sound.enabled
        await self._sync()
        await self._watch.run_while(on=on)

    async def state(self, settings: Settings) -> SoundState:
        root = self._context.root
        offered = await asyncio.to_thread(clock.crackles_after_sleep, root)
        objects = await self._dump()
        speakers = find_speakers(objects) if objects is not None else None
        return SoundState(
            speakers=speakers is not None,
            headphones=speakers is not None and not speakers.playing,
            running=objects is not None and filter_node(objects) is not None,
            clock_fix=offered or settings.clock_fix is True,
        )

    async def after_resume(self, settings: Settings) -> None:
        """Step the clock the moment the console wakes, before the slew makes the audio crackle."""
        if settings.clock_fix and await asyncio.to_thread(
            clock.crackles_after_sleep, self._context.root
        ):
            await clock.step()

    def stop(self) -> None:
        """Stop watching, and the filter with it, without waiting: Decky is unloading ORIGAMI."""
        self._watch.cancel()
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
            return
        try:
            run_blocking(
                "systemctl",
                "--user",
                "stop",
                UNIT,
                timeout=TIMEOUT_SECONDS,
                user=user,
                env=_session(user),
            )
        except TimeoutError as error:
            log.warning("Sound filter not stopped: %s", error)
        except CommandError as error:
            if error.returncode != UNIT_NOT_LOADED:
                log.warning("Sound filter not stopped: %s", error)
        try:
            (self._context.root / RUN_USER / str(user[0]) / CONFIG).unlink(missing_ok=True)
        except OSError as error:
            log.warning("Sound filter configuration not removed: %s", error)

    async def _keep(self) -> None:
        while True:
            await asyncio.sleep(POLL_SECONDS)
            await self._sync()

    async def _sync(self) -> None:
        async with self._lock:
            sound = self._sound
            owner = (await self._context.conflicts()).sound
            objects = await self._dump()
            speakers = find_speakers(objects) if objects is not None else None
            node = filter_node(objects) if objects is not None else None
            if (
                sound is None
                or not sound.enabled
                or owner is not None
                or speakers is None
                or not speakers.playing
            ):
                if node is not None:
                    await self._stop()
                return
            applied = self._applied
            if node is None or applied is None or speakers.sink != self._sink:
                await self._start(sound, speakers)
                return
            values = controls(sound)
            changed = {name: value for name, value in values.items() if applied.get(name) != value}
            if changed:
                await self._user_run(
                    "pw-cli", "set-param", str(node), "Props", set_param_props(changed)
                )
                self._applied = values

    async def _start(self, sound: Sound, speakers: Speakers) -> None:
        user = self._user()
        board = self._board()
        if user is None or board is None:
            return
        config = self._context.root / RUN_USER / str(user[0]) / CONFIG
        text = chain_config(SPEAKER_ZONES[board], speakers.sink, sound)
        await asyncio.to_thread(atomic_write_text, config, text)
        await self._stop()
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
        log.info("Sound filter started in front of %s: %s", speakers.sink, sound.to_json())

    async def _stop(self) -> None:
        try:
            await self._user_run("systemctl", "--user", "stop", UNIT)
        except CommandError as error:
            if error.returncode != UNIT_NOT_LOADED:
                log.warning("Sound filter not stopped: %s", error)
                return
        if self._applied is not None:
            log.info("Sound filter stopped")
        self._applied = None

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


def _session(user: tuple[int, int]) -> dict[str, str]:
    """What systemctl --user, systemd-run --user and the PipeWire tools need to find the session."""
    runtime = f"/run/user/{user[0]}"
    return {"XDG_RUNTIME_DIR": runtime, "DBUS_SESSION_BUS_ADDRESS": f"unix:path={runtime}/bus"}
