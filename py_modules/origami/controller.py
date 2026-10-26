# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""The Ally controller's HID interfaces that ORIGAMI talks to.

The hid-asus-ally driver binds HID interfaces 2 and 5 of the controller. On interface 2 the MCU
reports the special buttons and takes its settings as vendor feature reports `5a ...`, 64 bytes
long. Interface 5 is the gamepad itself, which takes the rumble output report. InputPlumber
hides both hidraw nodes from users; ORIGAMI uses them as root. Interface 3, bound by hid-asus,
is the controller's keyboard: held buttons arrive there as keys.
"""

import fcntl
import os
from collections.abc import Iterable
from pathlib import Path

from origami.sysfs import read_text

HIDRAW = Path("sys/class/hidraw")
DRIVER = "asus_rog_ally"
CONFIG_INTERFACE = "input2"
KEYBOARD_INTERFACE = "input3"
GAMEPAD_INTERFACE = "input5"
VENDOR_REPORT = 0x5A
REPORT_SIZE = 64


def find_hidraw(root: Path, interface: str) -> Path | None:
    """Find the node of one of the controller's interfaces; hidrawN changes between boots.

    The configuration interface is the one hid-asus-ally binds; the others are those of the same
    USB device, whichever driver binds them.
    """
    devices = _hid_devices(root)
    config = next(
        (
            phys
            for _, driver, phys in devices
            if driver == DRIVER and phys.endswith(f"/{CONFIG_INTERFACE}")
        ),
        None,
    )
    if config is None:
        return None
    wanted = config.removesuffix(CONFIG_INTERFACE) + interface
    return next((root / "dev" / node for node, _, phys in devices if phys == wanted), None)


def configure(root: Path, reports: Iterable[bytes]) -> None:
    """Send vendor feature reports to the MCU; raise OSError when the controller is not there."""
    path = find_hidraw(root, CONFIG_INTERFACE)
    if path is None:
        raise FileNotFoundError("The Ally controller's configuration interface is not there")
    send_feature_reports(path, reports)


def rumble(root: Path, report: bytes) -> None:
    """Write a rumble report to the gamepad; raise OSError when the controller is not there."""
    path = find_hidraw(root, GAMEPAD_INTERFACE)
    if path is None:
        raise FileNotFoundError("The Ally controller's gamepad interface is not there")
    fd = os.open(path, os.O_WRONLY | os.O_CLOEXEC)
    try:
        os.write(fd, report)
    finally:
        os.close(fd)


def _hid_devices(root: Path) -> list[tuple[str, str, str]]:
    """Every hidraw node with its driver and physical path, such as `usb-0000:66:00.0-4/input2`."""
    try:
        nodes = sorted((root / HIDRAW).iterdir())
    except OSError:
        return []
    devices: list[tuple[str, str, str]] = []
    for node in nodes:
        uevent = _parse_uevent(read_text(node / "device" / "uevent") or "")
        devices.append((node.name, uevent.get("DRIVER", ""), uevent.get("HID_PHYS", "")))
    return devices


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
