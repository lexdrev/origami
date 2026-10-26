# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import os
from pathlib import Path


class FakeRoot:
    """Fake filesystem root; attribute values end with a newline, as in sysfs."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, relative: str, value: object) -> Path:
        target = self.path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"{value}\n", encoding="utf-8")
        return target

    def hwmon(self, index: int, name: str, **attributes: object) -> Path:
        device = f"sys/class/hwmon/hwmon{index}"
        self.write(f"{device}/name", name)
        for attribute, value in attributes.items():
            self.write(f"{device}/{attribute}", value)
        return self.path / device

    def hidraw(self, index: int, *, driver: str, phys: str) -> Path:
        """Add a hidraw device; its node is a FIFO the test writes reports into."""
        self.write(
            f"sys/class/hidraw/hidraw{index}/device/uevent", f"DRIVER={driver}\nHID_PHYS={phys}"
        )
        node = self.path / "dev" / f"hidraw{index}"
        node.parent.mkdir(parents=True, exist_ok=True)
        os.mkfifo(node)
        return node

    def ally_controller(self) -> Path:
        """The controller's hidraw devices as on the console; returns the configuration node."""
        self.hidraw(0, driver="asus", phys="usb-0000:66:00.0-4/input0")
        self.hidraw(2, driver="asus", phys="usb-0000:66:00.0-4/input3")
        node = self.hidraw(5, driver="asus_rog_ally", phys="usb-0000:66:00.0-4/input2")
        self.hidraw(6, driver="asus_rog_ally", phys="usb-0000:66:00.0-4/input5")
        self.hidraw(7, driver="hid-generic", phys="")
        return node
