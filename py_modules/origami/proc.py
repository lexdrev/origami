# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import contextlib
import os
import subprocess


class CommandError(Exception):
    pass


def system_environment() -> dict[str, str]:
    """Environment for system binaries.

    Decky's Python is a PyInstaller bundle that points LD_LIBRARY_PATH at its own
    libraries; system tools such as busctl break with them. PyInstaller keeps the
    original value in LD_LIBRARY_PATH_ORIG.
    """
    env = dict(os.environ)
    original = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if original is None:
        env.pop("LD_LIBRARY_PATH", None)
    else:
        env["LD_LIBRARY_PATH"] = original
    return env


async def run(*args: str, user: tuple[int, int] | None = None) -> str:
    """Run a program without a shell and return its stdout; raise CommandError on failure.

    `user` (uid, gid) runs it as another user, which only root can do. Callers bound the time
    with asyncio.timeout(); on cancellation the program is killed.
    """
    uid, gid = user if user is not None else (None, None)
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=system_environment(),
            user=uid,
            group=gid,
            extra_groups=[] if user is not None else None,
        )
    except OSError as error:
        raise CommandError(f"Cannot start {args[0]}: {error.strerror}") from error
    try:
        stdout, stderr = await process.communicate()
    except asyncio.CancelledError:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        await process.wait()
        raise
    if process.returncode != 0:
        message = stderr.decode(errors="replace").strip()
        raise CommandError(f"{args[0]} exited with {process.returncode}: {message}")
    return stdout.decode(errors="replace")


def run_blocking(*args: str, timeout: float, user: tuple[int, int] | None = None) -> str:
    """run() for code that cannot await, such as what is undone while Decky unloads the plugin.

    Raise CommandError on failure and TimeoutError when the program takes longer than `timeout`.
    """
    uid, gid = user if user is not None else (None, None)
    try:
        result = subprocess.run(
            args,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env=system_environment(),
            user=uid,
            group=gid,
            extra_groups=[] if user is not None else None,
            timeout=timeout,
            check=False,
        )
    except OSError as error:
        raise CommandError(f"Cannot start {args[0]}: {error.strerror}") from error
    except subprocess.TimeoutExpired as error:
        raise TimeoutError(f"{args[0]} took longer than {timeout} s") from error
    if result.returncode != 0:
        message = result.stderr.decode(errors="replace").strip()
        raise CommandError(f"{args[0]} exited with {result.returncode}: {message}")
    return result.stdout.decode(errors="replace")
