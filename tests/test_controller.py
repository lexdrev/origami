# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

import pytest

from origami import controller
from origami.controller import find_config_hidraw, send_feature_reports

from fakes import FakeRoot


def test_finds_the_configuration_interface(fake_root: FakeRoot) -> None:
    node = fake_root.ally_controller()

    assert find_config_hidraw(fake_root.path) == node


def test_no_controller(fake_root: FakeRoot) -> None:
    assert find_config_hidraw(fake_root.path) is None


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
