# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""Presses of the Ally's own buttons, read from the controller's configuration interface.

The MCU reports these buttons as vendor reports `5a <code>`: one on press, `5a 00` about
1 ms later, and nothing while no button is pressed (HARDWARE.md, check 12).
"""

import asyncio
import errno
import logging
import os
from collections.abc import AsyncGenerator, Callable
from contextlib import aclosing
from enum import Enum
from pathlib import Path

from origami.controller import REPORT_SIZE, VENDOR_REPORT, find_config_hidraw

log = logging.getLogger(__name__)

BUTTON_CODE = 1
"""Index of the button code in a vendor report."""
RETRY_SECONDS = 5.0


class Button(Enum):
    QUICK_ACCESS = 0x93
    """Library, pressed shortly: Steam's quick access menu."""


def parse_press(report: bytes) -> Button | None:
    if len(report) <= BUTTON_CODE or report[0] != VENDOR_REPORT:
        return None
    try:
        return Button(report[BUTTON_CODE])
    except ValueError:
        return None


async def button_presses(
    root: Path, *, retry_seconds: float = RETRY_SECONDS
) -> AsyncGenerator[Button]:
    """Yield every press of a known button; look for the controller again when it goes away.

    The controller is reset on resume from sleep, and its node may come back under another number.
    """
    reported_missing = False
    while True:
        path = await asyncio.to_thread(find_config_hidraw, root)
        if path is None:
            if not reported_missing:
                log.warning("No configuration interface of the Ally controller; looking again")
                reported_missing = True
        else:
            reported_missing = False
            try:
                async with aclosing(_read_presses(path)) as presses:
                    async for button in presses:
                        yield button
            except OSError as error:
                log.warning("Stopped reading the Ally buttons on %s: %s", path, error)
        await asyncio.sleep(retry_seconds)


async def _read_presses(path: Path) -> AsyncGenerator[Button]:
    """Yield presses from one device node until it fails; reads only when the node has data."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    loop = asyncio.get_running_loop()
    events: asyncio.Queue[Button | OSError] = asyncio.Queue()
    loop.add_reader(fd, _drain, fd, events.put_nowait)
    log.info("Reading the Ally buttons on %s", path)
    try:
        while True:
            event = await events.get()
            if isinstance(event, OSError):
                raise event
            yield event
    finally:
        loop.remove_reader(fd)
        os.close(fd)


def _drain(fd: int, put: Callable[[Button | OSError], None]) -> None:
    """Read every report waiting on the node; hidraw returns one report per read."""
    while True:
        try:
            report = os.read(fd, REPORT_SIZE)
        except BlockingIOError:
            return
        except OSError as error:
            _fail(fd, put, error)
            return
        if not report:
            _fail(fd, put, OSError(errno.ENODEV, "The device node was closed"))
            return
        button = parse_press(report)
        if button is not None:
            put(button)


def _fail(fd: int, put: Callable[[Button | OSError], None], error: OSError) -> None:
    # A failed node stays readable; stop watching it so the loop does not spin until it is closed.
    asyncio.get_running_loop().remove_reader(fd)
    put(error)
