# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

import pytest

from origami import controller
from origami.controller import (
    CONFIG_INTERFACE,
    GAMEPAD_INTERFACE,
    KEYBOARD_INTERFACE,
    HidDevice,
    find_hid_device,
    find_hidraw,
    send_feature_reports,
)

from fakes import FakeRoot


def test_finds_the_configuration_interface(fake_root: FakeRoot) -> None:
    node = fake_root.ally_controller()

    assert find_hidraw(fake_root.path, CONFIG_INTERFACE) == node


def test_other_interfaces_are_those_of_the_same_controller(fake_root: FakeRoot) -> None:
    # Another ASUS device whose keyboard interface has the same number comes first.
    fake_root.hidraw(1, driver="asus", phys="usb-0000:66:00.0-3/input3")
    fake_root.ally_controller()

    assert find_hidraw(fake_root.path, KEYBOARD_INTERFACE) == fake_root.path / "dev" / "hidraw2"


def test_no_controller(fake_root: FakeRoot) -> None:
    fake_root.hidraw(1, driver="asus", phys="usb-0000:66:00.0-3/input3")

    assert find_hidraw(fake_root.path, CONFIG_INTERFACE) is None
    assert find_hidraw(fake_root.path, KEYBOARD_INTERFACE) is None
    assert find_hid_device(fake_root.path, GAMEPAD_INTERFACE) is None


def test_hid_device_of_an_interface_carries_the_kernels_number(fake_root: FakeRoot) -> None:
    fake_root.ally_controller()
    folder = fake_root.path / "sys/devices/hid/0003:0B05:1B4C.0007"

    assert find_hid_device(fake_root.path, GAMEPAD_INTERFACE) == HidDevice(id=7, path=folder)


def test_reports_go_out_as_64_byte_feature_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    node = tmp_path / "hidraw5"
    node.write_bytes(b"")
    calls: list[tuple[int, bytes]] = []

    def ioctl(_fd: int, request: int, buffer: bytes) -> None:
        calls.append((request, buffer))

    monkeypatch.setattr(controller.fcntl, "ioctl", ioctl)

    send_feature_reports(node, [bytes.fromhex("5ab4"), bytes.fromhex("5ab5")])

    # HIDIOCSFEATURE(64) as linux/hidraw.h computes it.
    assert calls == [
        (0xC0404806, bytes.fromhex("5ab4").ljust(64, b"\0")),
        (0xC0404806, bytes.fromhex("5ab5").ljust(64, b"\0")),
    ]
