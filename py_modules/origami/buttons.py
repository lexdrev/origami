# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Presses of the Ally's own buttons, read from the controller's HID interfaces.

The MCU reports short presses on the configuration interface as vendor reports `5a <code>`: one
on press, `5a 00` about 1 ms later. The upper left button held down comes from the controller's
keyboard interface as key F21, pressed and released within 1 ms. Both stay silent while no
button is pressed (HARDWARE.md, check 12).

The ROG Xbox Ally X20's MCU sends other codes (kernel 7.2.11-ogc4, hid-asus-ally, its rc74xa
branch): Library pressed shortly is 5a a0, and the upper left button held down comes as 5a 38 on
the configuration interface, not as a key. Not yet tried on an X20.
"""

import asyncio
import errno
import logging
import os
from collections.abc import AsyncGenerator, Callable, Iterable, Mapping
from contextlib import aclosing
from dataclasses import dataclass
from enum import Enum, StrEnum
from pathlib import Path

from origami.controller import (
    CONFIG_INTERFACE,
    KEYBOARD_INTERFACE,
    REPORT_SIZE,
    VENDOR_REPORT,
    find_hidraw,
)

log = logging.getLogger(__name__)

RETRY_SECONDS = 5.0


class Button(Enum):
    QUICK_ACCESS = "quick_access"
    """Library, pressed shortly: Steam's quick access menu."""
    ARMOURY_CRATE = "armoury_crate"
    """The upper left button, pressed shortly; nothing reaches Steam from it."""
    ARMOURY_CRATE_HOLD = "armoury_crate_hold"
    """The upper left button, held down; Steam gets it as L5 as well."""


class ButtonAction(StrEnum):
    """What ORIGAMI does on a press of a button it may drive."""

    NONE = "none"
    """ORIGAMI leaves the press alone."""
    ORIGAMI = "origami"
    QUICK_ACCESS = "quick_access"
    PERFORMANCE = "performance"
    OVERLAY = "overlay"
    """Steam's performance overlay, one level more detailed on every press, then off."""
    LIGHTING = "lighting"
    """The stick lighting, on or off."""
    SCREENSHOT = "screenshot"
    KEYBOARD = "keyboard"
    L5 = "l5"
    """Steam's L5, which holding the button gives it anyway; for the short press."""
    MAGNIFIER = "magnifier"
    CLOSE_GAME = "close_game"
    """The running game, after the button is held a second time."""


BUTTON_CODE = 1
"""Index of the button code in a vendor report."""
KEYBOARD_REPORT = 0x01
FIRST_KEY = 3
"""A keyboard report is: report id, modifiers, a reserved byte, then the keys held down."""


@dataclass(frozen=True, slots=True)
class Layout:
    """How a model's controller reports its buttons."""

    vendor_codes: Mapping[int, Button]
    """Button codes in the MCU's vendor reports on the configuration interface."""
    keyboard_keys: Mapping[int, Button]
    """HID usages of the keys it sends for its buttons on the keyboard interface."""

    def interface_of(self, button: Button) -> str:
        return KEYBOARD_INTERFACE if button in self.keyboard_keys.values() else CONFIG_INTERFACE


ALLY = Layout(
    vendor_codes={0x93: Button.QUICK_ACCESS, 0xA6: Button.ARMOURY_CRATE},
    keyboard_keys={0x70: Button.ARMOURY_CRATE_HOLD},  # 0x70 is F21
)
X20 = Layout(
    vendor_codes={
        0xA0: Button.QUICK_ACCESS,
        0xA6: Button.ARMOURY_CRATE,
        0x38: Button.ARMOURY_CRATE_HOLD,
    },
    keyboard_keys={},
)
LAYOUTS = {"RC74XA": X20}
"""Boards whose controller reports its buttons otherwise than the ROG Xbox Ally X's."""


def layout_for(board: str | None) -> Layout:
    return ALLY if board is None else LAYOUTS.get(board, ALLY)


type Parser = Callable[[bytes], Iterable[Button]]


def parse_press(report: bytes, layout: Layout = ALLY) -> Button | None:
    """The button a vendor report of the configuration interface announces."""
    if len(report) <= BUTTON_CODE or report[0] != VENDOR_REPORT:
        return None
    return layout.vendor_codes.get(report[BUTTON_CODE])


class KeyboardPresses:
    """Turns the keyboard interface's reports into presses: each report lists every key held."""

    def __init__(self, keys: Mapping[int, Button] = ALLY.keyboard_keys) -> None:
        self._keys = keys
        self._held: frozenset[int] = frozenset()

    def __call__(self, report: bytes) -> list[Button]:
        if len(report) <= FIRST_KEY or report[0] != KEYBOARD_REPORT:
            return []
        held = frozenset(report[FIRST_KEY:]) - {0}
        pressed, self._held = held - self._held, held
        return [self._keys[key] for key in sorted(pressed) if key in self._keys]


def _parser(interface: str, layout: Layout) -> Parser:
    if interface != CONFIG_INTERFACE:
        return KeyboardPresses(layout.keyboard_keys)

    def vendor_presses(report: bytes) -> list[Button]:
        button = parse_press(report, layout)
        return [] if button is None else [button]

    return vendor_presses


async def button_presses(
    root: Path,
    buttons: frozenset[Button],
    *,
    layout: Layout = ALLY,
    retry_seconds: float = RETRY_SECONDS,
) -> AsyncGenerator[Button]:
    """Yield every press of the given buttons; look for the controller again when it goes away.

    Only the interfaces those buttons come from are read. The controller is reset on resume from
    sleep, and its nodes may come back under other numbers.
    """
    interfaces = sorted({layout.interface_of(button) for button in buttons})
    reported_missing = False
    while True:
        found = {
            interface: await asyncio.to_thread(find_hidraw, root, interface)
            for interface in interfaces
        }
        paths = {interface: path for interface, path in found.items() if path is not None}
        if len(paths) < len(interfaces):
            if not reported_missing:
                log.warning("The Ally controller's button interfaces are not there; looking again")
                reported_missing = True
        else:
            reported_missing = False
            try:
                async with aclosing(_read_presses(paths, layout)) as presses:
                    async for button in presses:
                        if button in buttons:
                            yield button
            except OSError as error:
                log.warning("Stopped reading the Ally buttons: %s", error)
        await asyncio.sleep(retry_seconds)


async def _read_presses(paths: dict[str, Path], layout: Layout) -> AsyncGenerator[Button]:
    """Yield presses from the nodes until one fails; reads a node only when it has data."""
    loop = asyncio.get_running_loop()
    events: asyncio.Queue[Button | OSError] = asyncio.Queue()
    fds: list[int] = []
    try:
        for interface, path in paths.items():
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
            fds.append(fd)
            loop.add_reader(fd, _drain, fd, _parser(interface, layout), events.put_nowait)
        log.info("Reading the Ally buttons on %s", ", ".join(str(path) for path in paths.values()))
        while True:
            event = await events.get()
            if isinstance(event, OSError):
                raise event
            yield event
    finally:
        for fd in fds:
            loop.remove_reader(fd)
            os.close(fd)


def _drain(fd: int, parse: Parser, put: Callable[[Button | OSError], None]) -> None:
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
        for button in parse(report):
            put(button)


def _fail(fd: int, put: Callable[[Button | OSError], None], error: OSError) -> None:
    # A failed node stays readable; stop watching it so the loop does not spin until it is closed.
    asyncio.get_running_loop().remove_reader(fd)
    put(error)
