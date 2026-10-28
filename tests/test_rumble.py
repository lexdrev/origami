# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import shutil
from pathlib import Path

import pytest

from origami.rumble import OPS_MAP, RUMBLE_ITEMS, SETTINGS_MAP, RumbleProgram, RumbleSettings

from fakes import ALLY_X_GAMEPAD_DESCRIPTOR, FakeHidBpf, FakeRoot

PROGRAM = Path("/plugin/bin/rumble.bpf.o")
RIGHT_TRIGGER = RumbleSettings(right_trigger=60)


@pytest.fixture
def bpf() -> FakeHidBpf:
    return FakeHidBpf()


@pytest.fixture
def program(ally_x: FakeRoot, bpf: FakeHidBpf) -> RumbleProgram:
    ally_x.ally_controller()
    return RumbleProgram(ally_x.path, PROGRAM, bpf)


def replug_gamepad(root: FakeRoot, hid_id: int) -> None:
    """The gamepad interface comes back as a new HID device, as after a USB reset."""
    shutil.rmtree(root.path / "sys/class/hidraw/hidraw6")
    (root.path / "dev/hidraw6").unlink()
    root.hidraw(
        6,
        driver="asus_rog_ally",
        phys="usb-0000:66:00.0-4/input5",
        hid_id=hid_id,
        descriptor=ALLY_X_GAMEPAD_DESCRIPTOR,
    )


def test_settings_go_to_the_program_in_its_layout() -> None:
    # struct rumble_settings in bpf/rumble.bpf.c: left trigger, right trigger, grips, taps.
    assert RumbleSettings(left_trigger=30, right_trigger=60, grips=70).to_bytes() == bytes(
        [30, 60, 70, 0]
    )
    assert RumbleSettings(right_trigger=20, taps=True).to_bytes() == bytes([0, 20, 0, 1])
    assert RumbleSettings().idle()
    assert not RumbleSettings(grips=70).idle()


def test_the_ally_x_gamepad_lays_out_the_rumble_report_as_the_program_expects() -> None:
    # bpf/rumble.bpf.c rewrites bytes 2 to 5 of the report this describes.
    assert ALLY_X_GAMEPAD_DESCRIPTOR.index(RUMBLE_ITEMS) == 148


def test_program_goes_on_the_gamepad_interface_with_the_settings(
    program: RumbleProgram, bpf: FakeHidBpf
) -> None:
    program.apply(RIGHT_TRIGGER)
    program.apply(RumbleSettings(left_trigger=100, right_trigger=100, grips=70))

    [attached] = bpf.attached()
    assert (attached.path, attached.ops, attached.hid_id) == (PROGRAM, OPS_MAP, 7)
    assert attached.maps[SETTINGS_MAP] == [bytes([0, 60, 0, 0]), bytes([100, 100, 70, 0])]


def test_program_stays_for_the_grips_alone(program: RumbleProgram, bpf: FakeHidBpf) -> None:
    program.apply(RumbleSettings(grips=70))

    assert bpf.attached()[0].maps[SETTINGS_MAP] == [bytes([0, 0, 70, 0])]


def test_program_leaves_when_it_has_nothing_to_do(program: RumbleProgram, bpf: FakeHidBpf) -> None:
    program.apply(RumbleSettings())
    assert bpf.programs == []

    program.apply(RIGHT_TRIGGER)
    program.apply(RumbleSettings())

    assert bpf.attached() == []


def test_program_follows_the_gamepad_to_its_new_device(
    ally_x: FakeRoot, program: RumbleProgram, bpf: FakeHidBpf
) -> None:
    program.apply(RIGHT_TRIGGER)
    replug_gamepad(ally_x, hid_id=9)

    program.apply(RIGHT_TRIGGER)

    assert [(item.hid_id, item.closed) for item in bpf.programs] == [(7, True), (9, False)]


def test_program_is_not_attached_where_the_report_is_laid_out_otherwise(
    ally_x: FakeRoot, program: RumbleProgram, bpf: FakeHidBpf
) -> None:
    (ally_x.path / "sys/devices/hid/0003:0B05:1B4C.0007/report_descriptor").write_bytes(b"\x05")

    with pytest.raises(RuntimeError, match="rumble report"):
        program.apply(RIGHT_TRIGGER)

    assert bpf.programs == []


def test_no_program_without_the_controller(fake_root: FakeRoot, bpf: FakeHidBpf) -> None:
    program = RumbleProgram(fake_root.path, PROGRAM, bpf)

    with pytest.raises(FileNotFoundError):
        program.apply(RIGHT_TRIGGER)


def test_muted_triggers_get_their_strength_back_and_the_grips_stay_lifted(
    program: RumbleProgram, bpf: FakeHidBpf
) -> None:
    program.mute_triggers()  # nothing attached yet: nothing to do
    program.apply(RumbleSettings(right_trigger=60, grips=70))

    program.mute_triggers()
    program.unmute()

    assert bpf.attached()[0].maps[SETTINGS_MAP] == [
        bytes([0, 60, 70, 0]),
        bytes([0, 0, 70, 0]),
        bytes([0, 60, 70, 0]),
    ]


def test_closing_twice_is_harmless(program: RumbleProgram, bpf: FakeHidBpf) -> None:
    program.apply(RIGHT_TRIGGER)

    program.close()
    program.close()

    assert bpf.attached() == []
