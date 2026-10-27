# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from origami.triggers import (
    TriggerLevel,
    TriggerRumble,
    Triggers,
    TriggerState,
    pulse_report,
    read_trigger_state,
)

from fakes import FakeRoot

SOFT, MEDIUM = TriggerLevel.SOFT, TriggerLevel.MEDIUM
STRONG, MAX = TriggerLevel.STRONG, TriggerLevel.MAX


def on(triggers: Triggers, level: TriggerLevel) -> TriggerRumble:
    return TriggerRumble(enabled=True, triggers=triggers, level=level)


def test_triggers_stay_still_until_switched_on_then_rumble_the_right_at_the_middle() -> None:
    assert TriggerRumble() == TriggerRumble(enabled=False, triggers=Triggers.RIGHT, level=MEDIUM)
    assert TriggerRumble().strengths() == (0, 0)


def test_strength_of_each_trigger_at_each_level() -> None:
    assert on(Triggers.RIGHT, SOFT).strengths() == (0, 30)
    assert on(Triggers.RIGHT, MEDIUM).strengths() == (0, 60)
    assert on(Triggers.RIGHT, STRONG).strengths() == (0, 80)
    assert on(Triggers.BOTH, MAX).strengths() == (100, 100)


def test_off_keeps_the_triggers_and_the_level_for_later() -> None:
    off = TriggerRumble(enabled=False, triggers=Triggers.BOTH, level=MAX)

    assert off.strengths() == (0, 0)
    assert TriggerRumble.from_json(off.to_json()) == off


def test_json_round_trip() -> None:
    rumble = on(Triggers.BOTH, STRONG)

    assert TriggerRumble.from_json(rumble.to_json()) == rumble
    assert TriggerRumble.from_json({"enabled": True}) == on(Triggers.RIGHT, MEDIUM)


def test_settings_saved_before_the_switch() -> None:
    # Then "off" was one of the triggers, and a trigger meant on.
    off = TriggerRumble.from_json({"triggers": "off", "level": "soft"})
    both = TriggerRumble.from_json({"triggers": "both", "level": "medium"})

    assert off == TriggerRumble(level=SOFT)
    assert both == on(Triggers.BOTH, MEDIUM)


@pytest.mark.parametrize(
    "value",
    [
        None,
        {"triggers": "left"},
        {"enabled": True, "triggers": "off"},
        {"enabled": "yes"},
        {"triggers": "right", "level": "loud"},
        {"triggers": "right", "level": 60},
    ],
)
def test_bad_trigger_rumble_is_rejected(value: object) -> None:
    with pytest.raises(ValueError):
        TriggerRumble.from_json(value)


def test_the_test_pulse_drives_the_triggers_and_not_the_grips() -> None:
    assert pulse_report(on(Triggers.RIGHT, SOFT)) == bytes.fromhex("0d0f001e0000ff00eb")
    assert pulse_report(on(Triggers.BOTH, MAX)) == bytes.fromhex("0d0f64640000ff00eb")


def test_trigger_motors_on_the_ally_x(ally_x: FakeRoot) -> None:
    ally_x.ally_controller()

    assert read_trigger_state(ally_x.path, "RC73XA") is TriggerState.AVAILABLE
    assert read_trigger_state(ally_x.path, "RC73YA") is TriggerState.UNAVAILABLE
    assert read_trigger_state(ally_x.path, None) is TriggerState.UNAVAILABLE


def test_no_trigger_motors_without_the_controller_or_its_rumble_report(fake_root: FakeRoot) -> None:
    assert read_trigger_state(fake_root.path, "RC73XA") is TriggerState.UNAVAILABLE

    fake_root.ally_controller()
    (fake_root.path / "sys/devices/hid/0003:0B05:1B4C.0007/report_descriptor").write_bytes(b"\x05")

    assert read_trigger_state(fake_root.path, "RC73XA") is TriggerState.UNAVAILABLE
