# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio

import pytest

from origami.proc import CommandError
from origami.saturation import ATOM, from_cardinal, read_saturation, to_cardinal, write_saturation

from fakes import FakeDisplay, FakeRoot

SRGB = 1056964608
"""0.5 as a CARDINAL, what the console's display has while nothing else sets it."""


def test_percent_and_gamescope_value_convert_both_ways() -> None:
    assert to_cardinal(100) == SRGB
    assert from_cardinal(SRGB) == 100
    assert from_cardinal(to_cardinal(150)) == 150


def test_reads_the_value_gamescope_shows(fake_root: FakeRoot, display: FakeDisplay) -> None:
    display.properties[ATOM] = SRGB

    assert asyncio.run(read_saturation(fake_root.path)) == 100
    args, user = display.calls[0]
    assert args == ("xprop", "-display", ":0", "-root", "GAMESCOPE_COLOR_SDR_GAMUT_WIDENESS")
    assert user is not None


def test_writes_the_property_as_the_display_owner(
    fake_root: FakeRoot, display: FakeDisplay
) -> None:
    asyncio.run(write_saturation(fake_root.path, 150))

    args, user = display.calls[0]
    expected = ("xprop", "-display", ":0", "-root", "-f", ATOM, "32c", "-set", ATOM)
    assert args == (*expected, str(to_cardinal(150)))
    socket = (fake_root.path / "tmp/.X11-unix/X0").stat()
    assert user == (socket.st_uid, socket.st_gid)


def test_no_saturation_until_the_property_is_set(fake_root: FakeRoot, display: FakeDisplay) -> None:
    assert asyncio.run(read_saturation(fake_root.path)) is None
    assert display.calls


def test_without_gamescope_there_is_no_saturation(fake_root: FakeRoot) -> None:
    assert asyncio.run(read_saturation(fake_root.path)) is None
    with pytest.raises(CommandError):
        asyncio.run(write_saturation(fake_root.path, 150))
