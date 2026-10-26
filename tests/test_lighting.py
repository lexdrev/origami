# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

from collections.abc import Iterable
from pathlib import Path

import pytest

from origami import controller
from origami.lighting import (
    Brightness,
    Lighting,
    LightMode,
    Speed,
    apply_lighting,
    lighting_reports,
)

from fakes import FakeRoot

RED, BLUE = 0xFF0000, 0x0000FF
BRIGHTNESS_MEDIUM = bytes.fromhex("5abac5c402")
APPLY, STORE = bytes.fromhex("5ab4"), bytes.fromhex("5ab5")


def test_one_colour_goes_to_both_rings_at_once() -> None:
    reports = lighting_reports(Lighting(mode=LightMode.STATIC, left=0xFFB020, right=0xFFB020))

    assert reports == [
        BRIGHTNESS_MEDIUM,
        # 5a b3, zone 0, static, colour, no speed, direction, 00, breathing's second colour
        bytes.fromhex("5ab3 00 00 ffb020 00 00 00 000000"),
        APPLY,
        STORE,
    ]


def test_each_ring_gets_its_own_colour_on_its_two_halves() -> None:
    reports = lighting_reports(Lighting(mode=LightMode.STATIC, left=RED, right=BLUE))

    zones = [(report[2], report[4:7]) for report in reports[1:5]]
    assert zones == [
        (1, b"\xff\0\0"),
        (2, b"\xff\0\0"),
        (3, b"\0\0\xff"),
        (4, b"\0\0\xff"),
    ]


@pytest.mark.parametrize(
    ("mode", "speed", "code", "speed_code"),
    [
        (LightMode.BREATHING, Speed.SLOW, 1, 0xE1),
        (LightMode.RAINBOW, Speed.MEDIUM, 2, 0xEB),
        (LightMode.SPIRAL, Speed.FAST, 3, 0xF5),
    ],
)
def test_effects_carry_their_speed(
    mode: LightMode, speed: Speed, code: int, speed_code: int
) -> None:
    mode_report = lighting_reports(Lighting(mode=mode, speed=speed, left=RED, right=BLUE))[1]

    assert (mode_report[3], mode_report[7]) == (code, speed_code)


def test_rainbow_and_spiral_bring_their_own_colours() -> None:
    reports = lighting_reports(Lighting(mode=LightMode.SPIRAL, left=RED, right=BLUE))

    assert [report[2] for report in reports[1:-2]] == [0]


def test_off_is_static_black() -> None:
    assert lighting_reports(Lighting(enabled=False, mode=LightMode.SPIRAL, left=RED)) == [
        bytes.fromhex("5ab3 00 00 000000 00 00 00 000000"),
        APPLY,
        STORE,
    ]


def test_switching_on_starts_a_medium_spiral() -> None:
    lighting = Lighting()

    assert (lighting.enabled, lighting.mode) == (True, LightMode.SPIRAL)
    assert (lighting.speed, lighting.brightness) == (Speed.MEDIUM, Brightness.MEDIUM)


def test_lighting_survives_a_round_trip_through_json() -> None:
    value = Lighting(
        enabled=False,
        mode=LightMode.BREATHING,
        left=RED,
        right=BLUE,
        speed=Speed.FAST,
        brightness=Brightness.HIGH,
    )

    assert Lighting.from_json(value.to_json()) == value


def test_missing_keys_take_defaults_and_unknown_ones_are_skipped() -> None:
    assert Lighting.from_json({"mode": "rainbow", "future": 1}) == Lighting(mode=LightMode.RAINBOW)


@pytest.mark.parametrize(
    "value",
    [
        [],
        {"mode": "disco"},
        {"left": -1},
        {"right": 0x1000000},
        {"left": True},
        {"speed": 2},
        {"brightness": "off"},
        {"enabled": "yes"},
    ],
)
def test_bad_lighting_is_rejected(value: object) -> None:
    with pytest.raises(ValueError, match=r"lighting|enabled|mode|left|right|speed|brightness"):
        Lighting.from_json(value)


def test_apply_sends_the_commands_to_the_controller(
    ally_x: FakeRoot, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[tuple[Path, list[bytes]]] = []

    def send(path: Path, reports: Iterable[bytes]) -> None:
        sent.append((path, list(reports)))

    monkeypatch.setattr(controller, "send_feature_reports", send)
    node = ally_x.ally_controller()
    value = Lighting()

    apply_lighting(ally_x.path, value)

    assert sent == [(node, lighting_reports(value))]


def test_apply_fails_without_the_controller(fake_root: FakeRoot) -> None:
    with pytest.raises(FileNotFoundError):
        apply_lighting(fake_root.path, Lighting())
