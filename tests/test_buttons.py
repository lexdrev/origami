# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import os
from contextlib import aclosing
from pathlib import Path

import pytest

from origami.buttons import Button, button_presses, find_config_hidraw, parse_press

from fakes import FakeRoot

# Reports measured on the console (HARDWARE.md, check 12).
PRESS = bytes.fromhex("5a9300000000")
RELEASE = bytes.fromhex("5a0000000000")


def ally_controller(root: FakeRoot) -> Path:
    """The controller's interfaces as the console lists them; returns the configuration node."""
    root.hidraw(0, driver="asus", phys="usb-0000:66:00.0-4/input0")
    root.hidraw(2, driver="asus", phys="usb-0000:66:00.0-4/input3")
    node = root.hidraw(5, driver="asus_rog_ally", phys="usb-0000:66:00.0-4/input2")
    root.hidraw(6, driver="asus_rog_ally", phys="usb-0000:66:00.0-4/input5")
    root.hidraw(7, driver="hid-generic", phys="")
    return node


def test_finds_the_configuration_interface(fake_root: FakeRoot) -> None:
    node = ally_controller(fake_root)

    assert find_config_hidraw(fake_root.path) == node


def test_no_controller(fake_root: FakeRoot) -> None:
    assert find_config_hidraw(fake_root.path) is None


@pytest.mark.parametrize(
    ("report", "button"),
    [
        (PRESS, Button.QUICK_ACCESS),
        (RELEASE, None),
        (bytes.fromhex("5aa600000000"), None),
        (bytes.fromhex("0100007100"), None),
        (b"", None),
    ],
)
def test_reports(report: bytes, button: Button | None) -> None:
    assert parse_press(report) is button


def test_presses_are_read_and_the_controller_is_found_again(fake_root: FakeRoot) -> None:
    async def scenario() -> None:
        node = ally_controller(fake_root)
        writer = os.open(node, os.O_RDWR | os.O_NONBLOCK)
        async with aclosing(button_presses(fake_root.path, retry_seconds=0.01)) as presses:
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


def test_waits_for_the_controller(fake_root: FakeRoot, caplog: pytest.LogCaptureFixture) -> None:
    async def scenario() -> None:
        async with aclosing(button_presses(fake_root.path, retry_seconds=0.01)) as presses:
            next_press = asyncio.ensure_future(anext(presses))
            await asyncio.sleep(0.05)
            writer = os.open(ally_controller(fake_root), os.O_RDWR | os.O_NONBLOCK)
            await asyncio.sleep(0.05)
            os.write(writer, PRESS)
            assert await asyncio.wait_for(next_press, 1) is Button.QUICK_ACCESS
        os.close(writer)

    asyncio.run(scenario())
    assert caplog.text.count("No configuration interface") == 1
