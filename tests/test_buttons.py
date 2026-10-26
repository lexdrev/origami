# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import os
from contextlib import aclosing

import pytest

from origami.buttons import Button, KeyboardPresses, button_presses, parse_press

from fakes import FakeRoot

# Reports measured on the console (HARDWARE.md, check 12).
PRESS = bytes.fromhex("5a9300000000")
RELEASE = bytes.fromhex("5a0000000000")
HOLD = bytes.fromhex("0100007000000000")
LET_GO = bytes.fromhex("0100000000000000")

QUICK_ACCESS = frozenset({Button.QUICK_ACCESS})


@pytest.mark.parametrize(
    ("report", "button"),
    [
        (PRESS, Button.QUICK_ACCESS),
        (bytes.fromhex("5aa600000000"), Button.ARMOURY_CRATE),
        (RELEASE, None),
        (bytes.fromhex("5aa700000000"), None),
        (HOLD, None),
        (b"", None),
    ],
)
def test_vendor_reports(report: bytes, button: Button | None) -> None:
    assert parse_press(report) is button


def test_a_held_key_is_one_press() -> None:
    presses = KeyboardPresses()

    assert presses(HOLD) == [Button.ARMOURY_CRATE_HOLD]
    # The same key still held while another one comes and goes.
    assert presses(bytes.fromhex("0100007069000000")) == []
    assert presses(HOLD) == []
    assert presses(LET_GO) == []
    assert presses(HOLD) == [Button.ARMOURY_CRATE_HOLD]


@pytest.mark.parametrize(
    "report", [bytes.fromhex("0100007100000000"), PRESS, bytes.fromhex("010000")]
)
def test_other_keys_and_reports_are_no_press(report: bytes) -> None:
    assert KeyboardPresses()(report) == []


def test_presses_are_read_and_the_controller_is_found_again(fake_root: FakeRoot) -> None:
    async def scenario() -> None:
        node = fake_root.ally_controller()
        writer = os.open(node, os.O_RDWR | os.O_NONBLOCK)
        async with aclosing(
            button_presses(fake_root.path, QUICK_ACCESS, retry_seconds=0.01)
        ) as presses:
            next_press = asyncio.ensure_future(anext(presses))
            os.write(writer, PRESS)
            assert await asyncio.wait_for(next_press, 1) is Button.QUICK_ACCESS

            # The node closes, as on resume from sleep, and comes back.
            os.close(writer)
            next_press = asyncio.ensure_future(anext(presses))
            await asyncio.sleep(0.05)
            writer = os.open(node, os.O_RDWR | os.O_NONBLOCK)
            os.write(writer, PRESS)
            assert await asyncio.wait_for(next_press, 1) is Button.QUICK_ACCESS
        os.close(writer)

    asyncio.run(scenario())


def test_both_interfaces_are_read_for_the_armoury_crate_button(fake_root: FakeRoot) -> None:
    async def scenario() -> None:
        config = fake_root.ally_controller()
        keyboard = fake_root.path / "dev" / "hidraw2"
        config_writer = os.open(config, os.O_RDWR | os.O_NONBLOCK)
        keyboard_writer = os.open(keyboard, os.O_RDWR | os.O_NONBLOCK)
        buttons = frozenset({Button.ARMOURY_CRATE, Button.ARMOURY_CRATE_HOLD})
        async with aclosing(button_presses(fake_root.path, buttons)) as presses:
            next_press = asyncio.ensure_future(anext(presses))
            await asyncio.sleep(0.05)
            # Library is not among the buttons asked for.
            os.write(config_writer, PRESS)
            os.write(keyboard_writer, HOLD)
            assert await asyncio.wait_for(next_press, 1) is Button.ARMOURY_CRATE_HOLD

            os.write(config_writer, bytes.fromhex("5aa600000000"))
            assert await asyncio.wait_for(anext(presses), 1) is Button.ARMOURY_CRATE
        os.close(config_writer)
        os.close(keyboard_writer)

    asyncio.run(scenario())


def test_waits_for_the_controller(fake_root: FakeRoot, caplog: pytest.LogCaptureFixture) -> None:
    async def scenario() -> None:
        async with aclosing(
            button_presses(fake_root.path, QUICK_ACCESS, retry_seconds=0.01)
        ) as presses:
            next_press = asyncio.ensure_future(anext(presses))
            await asyncio.sleep(0.05)
            writer = os.open(fake_root.ally_controller(), os.O_RDWR | os.O_NONBLOCK)
            await asyncio.sleep(0.05)
            os.write(writer, PRESS)
            assert await asyncio.wait_for(next_press, 1) is Button.QUICK_ACCESS
        os.close(writer)

    asyncio.run(scenario())
    assert caplog.text.count("button interfaces are not there") == 1
