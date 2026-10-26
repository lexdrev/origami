# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""The configuration interface of the Ally controller.

The hid-asus-ally driver binds HID interface 2 of the controller. The MCU reports the
special buttons there and takes its settings there as vendor feature reports `5a ...`,
64 bytes long. InputPlumber hides the hidraw node from users; ORIGAMI uses it as root.
"""

import fcntl
import os
from collections.abc import Iterable
from pathlib import Path

from origami.sysfs import read_text

HIDRAW = Path("sys/class/hidraw")
DRIVER = "asus_rog_ally"
CONFIG_INTERFACE = "input2"
VENDOR_REPORT = 0x5A
REPORT_SIZE = 64


def find_config_hidraw(root: Path) -> Path | None:
    """Find the node of the controller's configuration interface; hidrawN changes between boots."""
    try:
        nodes = sorted((root / HIDRAW).iterdir())
    except OSError:
        return None
    for node in nodes:
        uevent = _parse_uevent(read_text(node / "device" / "uevent") or "")
        if uevent.get("DRIVER") == DRIVER and uevent.get("HID_PHYS", "").endswith(
            f"/{CONFIG_INTERFACE}"
        ):
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
