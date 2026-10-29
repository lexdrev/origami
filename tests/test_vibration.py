# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from collections.abc import Iterable
from pathlib import Path

import pytest

from origami import controller
from origami.jsonio import JsonValue
from origami.vibration import (
    Vibration,
    apply_vibration,
    original_vibration,
    read_driver_strength,
    start_pulse,
    stop_rumble,
    strength_report,
)

from fakes import FakeRoot


def test_strength_goes_to_the_mcu_as_command_6() -> None:
    assert strength_report(Vibration(left=40, right=100)) == bytes.fromhex("5ad10602 28 64")


def test_half_strength_by_default() -> None:
    assert Vibration() == Vibration(enabled=True, left=50, right=50)


def test_off_keeps_the_strength_for_later_and_sends_zero() -> None:
    off = Vibration(enabled=False, left=40, right=60)

    assert strength_report(off) == bytes.fromhex("5ad10602 00 00")
    assert Vibration.from_json(off.to_json()) == off
    # Settings saved before the switch existed have no "enabled": the handles were on.
    assert Vibration.from_json({"left": 40, "right": 60}) == Vibration(left=40, right=60)


def test_vibration_survives_a_round_trip_through_json() -> None:
    value = Vibration(left=0, right=75)

    assert Vibration.from_json(value.to_json()) == value


@pytest.mark.parametrize(
    "value",
    [[], {"left": 101}, {"right": -1}, {"left": True}, {"right": "50"}],
)
def test_bad_vibration_is_rejected(value: object) -> None:
    with pytest.raises(ValueError, match=r"vibration|left|right"):
        Vibration.from_json(value)


def test_apply_sends_the_strength_to_the_configuration_interface(
    ally_x: FakeRoot, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[tuple[Path, list[bytes]]] = []

    def send(path: Path, reports: Iterable[bytes]) -> None:
        sent.append((path, list(reports)))

    monkeypatch.setattr(controller, "send_feature_reports", send)
    node = ally_x.ally_controller()

    apply_vibration(ally_x.path, Vibration(left=30, right=30))

    assert sent == [(node, [bytes.fromhex("5ad10602 1e 1e")])]


def test_apply_fails_without_the_controller(fake_root: FakeRoot) -> None:
    with pytest.raises(FileNotFoundError):
        apply_vibration(fake_root.path, Vibration())


def test_the_pulse_rumbles_the_handles_until_it_is_stopped(ally_x: FakeRoot) -> None:
    ally_x.ally_controller()
    gamepad = ally_x.path / "dev" / "hidraw6"
    reader = os.open(gamepad, os.O_RDONLY | os.O_NONBLOCK)
    try:
        start_pulse(ally_x.path)
        stop_rumble(ally_x.path)

        # Both handles at a strong game rumble, the triggers still; then all at zero.
        assert os.read(reader, 64) == bytes.fromhex("0d0f 0000 2020 ff00eb 0d0f 0000 0000 ff00eb")
    finally:
        os.close(reader)


def test_the_driver_reports_the_strength_it_took(ally_x: FakeRoot) -> None:
    assert read_driver_strength(ally_x.path) == (50, 50)


def test_no_strength_without_the_driver(fake_root: FakeRoot) -> None:
    assert read_driver_strength(fake_root.path) is None


@pytest.mark.parametrize(
    ("original", "strength"),
    [
        ([40, 60], (40, 60)),
        (None, (100, 100)),
        ([40], (100, 100)),
        ([True, 60], (100, 100)),
        ([40, 160], (100, 100)),
    ],
)
def test_the_original_strength_is_the_drivers_or_the_mcus_own(
    original: JsonValue, strength: tuple[int, int]
) -> None:
    assert original_vibration(original).strengths() == strength
