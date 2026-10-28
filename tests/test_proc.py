# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import sys
from pathlib import Path

import pytest

from origami.proc import CommandError, run, run_blocking, system_environment


def test_pyinstaller_library_path_is_restored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LD_LIBRARY_PATH", "/opt/bundle/lib")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/usr/local/lib")

    env = system_environment()

    assert env["LD_LIBRARY_PATH"] == "/usr/local/lib"
    assert "LD_LIBRARY_PATH_ORIG" not in env


def test_bundled_library_path_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LD_LIBRARY_PATH", "/opt/bundle/lib")
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)

    assert "LD_LIBRARY_PATH" not in system_environment()


def test_stdout_is_returned() -> None:
    assert asyncio.run(run(sys.executable, "-c", "print('ok')")).strip() == "ok"


def test_failure_carries_stderr() -> None:
    script = "import sys; sys.stderr.write('broken'); sys.exit(3)"

    with pytest.raises(CommandError, match="exited with 3: broken"):
        asyncio.run(run(sys.executable, "-c", script))


def test_missing_program() -> None:
    with pytest.raises(CommandError, match="Cannot start origami-no-such-program"):
        asyncio.run(run("origami-no-such-program"))


@pytest.mark.skipif(sys.platform != "linux", reason="looks the process up in /proc")
def test_cancellation_kills_the_program(tmp_path: Path) -> None:
    pid_file = tmp_path / "pid"
    script = (
        "import os, pathlib, time; "
        f"pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid())); "
        "time.sleep(60)"
    )

    async def scenario() -> None:
        async with asyncio.timeout(1.5):
            await run(sys.executable, "-c", script)

    with pytest.raises(TimeoutError):
        asyncio.run(scenario())

    assert not Path("/proc", pid_file.read_text()).exists()


def test_blocking_run_returns_stdout_and_carries_stderr() -> None:
    assert run_blocking(sys.executable, "-c", "print('ok')", timeout=10).strip() == "ok"
    with pytest.raises(CommandError, match="exited with 3: broken"):
        script = "import sys; sys.stderr.write('broken'); sys.exit(3)"
        run_blocking(sys.executable, "-c", script, timeout=10)
    with pytest.raises(CommandError, match="Cannot start origami-no-such-program"):
        run_blocking("origami-no-such-program", timeout=10)


def test_blocking_run_stops_waiting_at_its_timeout() -> None:
    with pytest.raises(TimeoutError):
        run_blocking(sys.executable, "-c", "import time; time.sleep(60)", timeout=0.5)
