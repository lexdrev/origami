# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Ally controller's HID interfaces that ORIGAMI talks to.

The hid-asus-ally driver binds HID interfaces 2 and 5 of the controller. On interface 2 the MCU
reports the special buttons and takes its settings as vendor feature reports `5a ...`, 64 bytes
long. Interface 5 is the gamepad itself, which takes the rumble output report. InputPlumber
hides both hidraw nodes from users; ORIGAMI uses them as root.
"""

import fcntl
import os
from collections.abc import Iterable
from pathlib import Path

from origami.sysfs import read_text

HIDRAW = Path("sys/class/hidraw")
DRIVER = "asus_rog_ally"
CONFIG_INTERFACE = "input2"
GAMEPAD_INTERFACE = "input5"
VENDOR_REPORT = 0x5A
REPORT_SIZE = 64


def find_config_hidraw(root: Path) -> Path | None:
    """Find the node of the controller's configuration interface; hidrawN changes between boots."""
    return _find_hidraw(root, CONFIG_INTERFACE)


def configure(root: Path, reports: Iterable[bytes]) -> None:
    """Send vendor feature reports to the MCU; raise OSError when the controller is not there."""
    path = find_config_hidraw(root)
    if path is None:
        raise FileNotFoundError("The Ally controller's configuration interface is not there")
    send_feature_reports(path, reports)


def rumble(root: Path, report: bytes) -> None:
    """Write a rumble report to the gamepad; raise OSError when the controller is not there."""
    path = _find_hidraw(root, GAMEPAD_INTERFACE)
    if path is None:
        raise FileNotFoundError("The Ally controller's gamepad interface is not there")
    fd = os.open(path, os.O_WRONLY | os.O_CLOEXEC)
    try:
        os.write(fd, report)
    finally:
        os.close(fd)


def _find_hidraw(root: Path, interface: str) -> Path | None:
    try:
        nodes = sorted((root / HIDRAW).iterdir())
    except OSError:
        return None
    for node in nodes:
        uevent = _parse_uevent(read_text(node / "device" / "uevent") or "")
        if uevent.get("DRIVER") == DRIVER and uevent.get("HID_PHYS", "").endswith(f"/{interface}"):
            return root / "dev" / node.name
    return None


def _parse_uevent(text: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def send_feature_reports(path: Path, reports: Iterable[bytes]) -> None:
    """Send vendor feature reports in order, as the driver does (HIDIOCSFEATURE)."""
    fd = os.open(path, os.O_RDWR | os.O_CLOEXEC)
    try:
        for report in reports:
            fcntl.ioctl(fd, _set_feature(REPORT_SIZE), report.ljust(REPORT_SIZE, b"\0"))
    finally:
        os.close(fd)


def _set_feature(length: int) -> int:
    # HIDIOCSFEATURE(len) from linux/hidraw.h: _IOC(_IOC_READ | _IOC_WRITE, 'H', 0x06, len).
    return (3 << 30) | (length << 16) | (ord("H") << 8) | 0x06
