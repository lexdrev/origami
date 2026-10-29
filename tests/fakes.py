# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
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

    def hidraw(
        self,
        index: int,
        *,
        driver: str,
        phys: str,
        hid_id: int | None = None,
        descriptor: bytes = b"",
    ) -> Path:
        """Add a hidraw device; its node is a FIFO the test writes reports into.

        As in sysfs, hidrawN/device links to the HID device's folder, named by its id.
        """
        number = 0x100 + index if hid_id is None else hid_id
        device = self.path / "sys/devices/hid" / f"0003:0B05:1B4C.{number:04X}"
        self.write(f"{device.relative_to(self.path)}/uevent", f"DRIVER={driver}\nHID_PHYS={phys}")
        (device / "report_descriptor").write_bytes(descriptor)
        hidraw = self.path / "sys/class/hidraw" / f"hidraw{index}"
        hidraw.mkdir(parents=True)
        (hidraw / "device").symlink_to(device)
        node = self.path / "dev" / f"hidraw{index}"
        node.parent.mkdir(parents=True, exist_ok=True)
        os.mkfifo(node)
        return node

    def ally_controller(self) -> Path:
        """The controller's hidraw devices as on the console; returns the configuration node."""
        self.hidraw(0, driver="asus", phys="usb-0000:66:00.0-4/input0", hid_id=1)
        self.hidraw(2, driver="asus", phys="usb-0000:66:00.0-4/input3", hid_id=5)
        node = self.hidraw(5, driver="asus_rog_ally", phys="usb-0000:66:00.0-4/input2", hid_id=3)
        self.hidraw(
            6,
            driver="asus_rog_ally",
            phys="usb-0000:66:00.0-4/input5",
            hid_id=7,
            descriptor=ALLY_X_GAMEPAD_DESCRIPTOR,
        )
        self.hidraw(7, driver="hid-generic", phys="", hid_id=8)
        return node


ALLY_X_GAMEPAD_DESCRIPTOR = bytes.fromhex(
    "05010905a101850ba10009300931150026ffff350046ffff950275108102c0a10009330934150026"
    "ffff950275108102c005010932150026ff039501750a810215002500750695018103050109351500"
    "26ff039501750a81021500250075069501810305091901290e150025017501950e81029501750281"
    "0105010939150125083500463b016514750495018102950175048101050f0921850da10209971500"
    "2501750495019102150025007504950191030970150025647508950491020950660110550e150026"
    "ff0075089501910209a7150026ff0075089501910265005500097c150026ff00750895019102c0c0"
)
"""Report descriptor of the Ally X gamepad interface (input5), read on the console."""


class FakeBpfProgram:
    """A HID-BPF program as the kernel would hold it: where it is attached and its map values."""

    def __init__(self, path: Path, ops: str, hid_id: int) -> None:
        self.path = path
        self.ops = ops
        self.hid_id = hid_id
        self.maps: dict[str, list[bytes]] = {}
        self.closed = False

    def update(self, map_name: str, key: bytes, value: bytes) -> None:
        assert not self.closed
        assert key == bytes(4)
        self.maps.setdefault(map_name, []).append(value)

    def close(self) -> None:
        self.closed = True


class FakeHidBpf:
    """Attaches fake HID-BPF programs, in place of libbpf."""

    def __init__(self) -> None:
        self.programs: list[FakeBpfProgram] = []

    def __call__(self, path: Path, ops: str, hid_id: int) -> FakeBpfProgram:
        program = FakeBpfProgram(path, ops, hid_id)
        self.programs.append(program)
        return program

    def attached(self) -> list[FakeBpfProgram]:
        return [program for program in self.programs if not program.closed]


class FakeDisplay:
    """gamescope's root window as xprop sees it: CARDINAL properties by name, and every call."""

    def __init__(self) -> None:
        self.properties: dict[str, int] = {}
        self.calls: list[tuple[tuple[str, ...], tuple[int, int] | None]] = []

    async def run(self, *args: str, user: tuple[int, int] | None = None) -> str:
        return self._answer(args, user)

    def run_blocking(self, *args: str, timeout: float, user: tuple[int, int] | None = None) -> str:
        assert timeout > 0
        return self._answer(args, user)

    def _answer(self, args: tuple[str, ...], user: tuple[int, int] | None) -> str:
        self.calls.append((args, user))
        if "-set" in args:
            self.properties[args[-2]] = int(args[-1])
            return ""
        atom = args[-1]
        if atom not in self.properties:
            return f"{atom}:  not found.\n"
        return f"{atom}(CARDINAL) = {self.properties[atom]}\n"
