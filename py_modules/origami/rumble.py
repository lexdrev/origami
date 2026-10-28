# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""The rumble program: HID-BPF on the gamepad's rumble report (bpf/rumble.bpf.c).

InputPlumber writes the controller's rumble report 0x0D with the strength Steam asks for. On its
way to the controller the program fills the impulse triggers from the grips (B19) and lifts the
grips, at the strengths ORIGAMI writes into the program's settings map. The program sits on the
controller only while it has something to do.
"""

import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from origami.controller import GAMEPAD_INTERFACE, find_hid_device

PROGRAM = Path("bin/rumble.bpf.o")
"""The compiled program, in the plugin's folder."""
OPS_MAP = "rumble_ops"
SETTINGS_MAP = "settings"
_SETTINGS_KEY = bytes(4)

# How the gamepad's report descriptor describes the rumble report 0x0D: motor enable bits, then the
# strengths of the left trigger, right trigger, left grip and right grip, 0-100 each. The program
# rewrites those bytes, so it is attached only where the report is laid out like this.
RUMBLE_ITEMS = bytes.fromhex(
    "050f0921850da102"  # Usage Page (Physical Interface Device), Set Effect Report, Report ID 13
    "09971500250175049501910215002500750495019103"  # DC Enable Actuators: 4 bits, 4 bits padding
    "097015002564750895049102"  # Magnitude: 4 bytes, 0-100
)


@dataclass(frozen=True, slots=True)
class RumbleSettings:
    """Strengths at a game's full rumble, in percent, as bpf/rumble.bpf.c reads them."""

    left_trigger: int = 0
    """0 keeps the trigger still."""
    right_trigger: int = 0
    grips: int = 0
    """0 leaves the grips as the game sent them."""
    taps: bool = False
    """The triggers tap once on each shot instead of following the grips."""

    def idle(self) -> bool:
        return not (self.left_trigger or self.right_trigger or self.grips)

    def without_triggers(self) -> RumbleSettings:
        return replace(self, left_trigger=0, right_trigger=0)

    def to_bytes(self) -> bytes:
        return bytes([self.left_trigger, self.right_trigger, self.grips, self.taps])


def lays_out_rumble(device: Path) -> bool:
    """Whether the HID device in this sysfs folder has the rumble report the program rewrites."""
    try:
        return RUMBLE_ITEMS in (device / "report_descriptor").read_bytes()
    except OSError:
        return False


class AttachedProgram(Protocol):
    hid_id: int

    def update(self, map_name: str, key: bytes, value: bytes) -> None: ...

    def close(self) -> None: ...


class Attach(Protocol):
    def __call__(self, path: Path, ops: str, hid_id: int) -> AttachedProgram: ...


class RumbleProgram:
    """The rumble program on the controller's gamepad interface, attached while it has work.

    The kernel takes the program off when the interface goes away, and the interface comes back
    under a new id, so every apply checks that the program sits on the current one. Worker threads
    and the event loop both call in, so one lock keeps them off libbpf's object at the same time.
    """

    def __init__(self, root: Path, program: Path, attach: Attach) -> None:
        self._root = root
        self._program = program
        self._attach = attach
        self._lock = threading.Lock()
        self._attached: AttachedProgram | None = None
        self._settings = RumbleSettings()

    def apply(self, settings: RumbleSettings) -> None:
        """Rewrite rumble as set; raise OSError or RuntimeError when the program cannot work."""
        with self._lock:
            if settings.idle():
                self._close()
                return
            device = find_hid_device(self._root, GAMEPAD_INTERFACE)
            if device is None:
                raise FileNotFoundError("The Ally controller's gamepad interface is not there")
            if self._attached is not None and self._attached.hid_id != device.id:
                self._close()
            if self._attached is None:
                if not lays_out_rumble(device.path):
                    raise RuntimeError("The controller lays out its rumble report differently")
                self._attached = self._attach(self._program, OPS_MAP, device.id)
            self._settings = settings
            self._attached.update(SETTINGS_MAP, _SETTINGS_KEY, settings.to_bytes())

    def mute_triggers(self) -> None:
        """Keep the triggers still until unmute; the grips keep their strength."""
        with self._lock:
            if self._attached is not None:
                value = self._settings.without_triggers().to_bytes()
                self._attached.update(SETTINGS_MAP, _SETTINGS_KEY, value)

    def unmute(self) -> None:
        with self._lock:
            if self._attached is not None:
                self._attached.update(SETTINGS_MAP, _SETTINGS_KEY, self._settings.to_bytes())

    def close(self) -> None:
        with self._lock:
            self._close()

    def _close(self) -> None:
        if self._attached is not None:
            self._attached.close()
            self._attached = None
