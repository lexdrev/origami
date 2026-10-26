# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio

import pytest

from origami.magnifier import ATOM, toggle_magnifier
from origami.proc import CommandError

from fakes import FakeDisplay, FakeRoot

# What Steam writes while Steam + L1 is held, and after (measured on the console).
ONE_AND_A_HALF = 98302
ONE = 65535


def test_one_press_magnifies_as_steam_does_and_the_next_one_stops(
    fake_root: FakeRoot, display: FakeDisplay
) -> None:
    display.properties[ATOM] = ONE

    assert asyncio.run(toggle_magnifier(fake_root.path)) is True
    assert display.properties[ATOM] == ONE_AND_A_HALF

    assert asyncio.run(toggle_magnifier(fake_root.path)) is False
    assert display.properties[ATOM] == ONE


def test_magnifies_before_steam_ever_set_the_property(
    fake_root: FakeRoot, display: FakeDisplay
) -> None:
    assert asyncio.run(toggle_magnifier(fake_root.path)) is True
    assert display.properties[ATOM] == ONE_AND_A_HALF


def test_no_magnifier_without_gamescope(fake_root: FakeRoot) -> None:
    with pytest.raises(CommandError):
        asyncio.run(toggle_magnifier(fake_root.path))
