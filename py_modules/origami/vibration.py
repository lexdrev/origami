# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""Strength of the handle vibration.

The MCU scales every rumble by its own strength, 0-100 for each handle; from the factory it is
100. The hid-asus-ally driver on kernel 7.2.9-ogc3 takes only 0-64 through
vibration_intensity (it compares with 64 where 0x64 was meant), so ORIGAMI sends the MCU command
itself. In sleep the MCU loses power and wakes at 100 again, and the driver does not send the
strength back, so ORIGAMI sends it after every resume (BUGS.md, B01).

Steam asks for every rumble at -5 dB, so a game's full rumble reaches a grip as only about 32 of
100, and even at 100 the handles felt weak in games. The rumble program (origami.rumble) lifts the
grips to GRIP_AT_GAME_FULL; the MCU's strength then scales that, so the whole scale reaches games.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from origami.controller import VENDOR_REPORT, configure, rumble
from origami.jsonio import JsonValue, expect_bool
from origami.sysfs import read_text

MAX_STRENGTH = 100
DEFAULT_STRENGTH = 50
GRIP_AT_GAME_FULL = 70
"""Strength of a grip at a game's full rumble before the MCU's strength; 32 without the lift."""
DRIVER_STRENGTH = Path("sys/module/hid_asus_ally/drivers/hid:asus_rog_ally")
"""Holds one device folder per controller with vibration_intensity, the driver's copy."""


@dataclass(frozen=True, slots=True)
class Vibration:
    enabled: bool = True
    """Off keeps the handles still; the strengths wait for the next time it is on."""
    left: int = DEFAULT_STRENGTH
    """Strength of the left handle's motor in percent."""
    right: int = DEFAULT_STRENGTH

    @classmethod
    def from_json(cls, value: object) -> Vibration:
        """Parse vibration sent by the frontend or saved; raise ValueError on bad input."""
        if not isinstance(value, dict):
            raise ValueError("vibration must be an object")
        data = cast("dict[str, object]", value)
        defaults = cls()
        return cls(
            enabled=expect_bool("enabled", data.get("enabled", defaults.enabled)),
            left=_strength("left", data.get("left", defaults.left)),
            right=_strength("right", data.get("right", defaults.right)),
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {"enabled": self.enabled, "left": self.left, "right": self.right}

    def strengths(self) -> tuple[int, int]:
        """What the MCU gets for the left and the right handle."""
        return (self.left, self.right) if self.enabled else (0, 0)


def original_vibration(original: JsonValue) -> Vibration:
    """The strength the driver held before ORIGAMI, as the journal keeps it; else the MCU's 100."""
    match original:
        case [int() as left, int() as right] if all(
            not isinstance(value, bool) and 0 <= value <= MAX_STRENGTH for value in (left, right)
        ):
            return Vibration(left=left, right=right)
        case _:
            return Vibration(left=MAX_STRENGTH, right=MAX_STRENGTH)


def _strength(key: str, value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_STRENGTH:
        return value
    raise ValueError(f"{key} must be a strength from 0 to {MAX_STRENGTH}")


# 5a d1 06 02 <left> <right>: the MCU's vibration strength (command 6, two bytes of data).
STRENGTH = bytes([VENDOR_REPORT, 0xD1, 0x06, 0x02])


def strength_report(vibration: Vibration) -> bytes:
    return STRENGTH + bytes(vibration.strengths())


def apply_vibration(root: Path, vibration: Vibration) -> None:
    """Send the strength to the controller; raise OSError when it cannot be reached."""
    configure(root, [strength_report(vibration)])


# The gamepad's rumble report, the same InputPlumber writes:
#   0d 0f <left trigger> <right trigger> <left handle> <right handle> ff 00 eb
# The last three bytes are times in the Xbox format, but the Ally's MCU ignores them: a rumble
# runs until the next report, so a pulse has to be stopped with a report of zeros.
PULSE_MAGNITUDE = 32
"""The strongest rumble of a game as InputPlumber passes it on: about 32 of 100 at Steam's -5 dB.

The rumble program lifts the test pulse as it lifts a game's rumble."""
PULSE_SECONDS = 1.0


def rumble_report(magnitude: int) -> bytes:
    """Both handles at the magnitude, the triggers still."""
    return bytes([0x0D, 0x0F, 0, 0, magnitude, magnitude, 0xFF, 0x00, 0xEB])


def start_pulse(root: Path) -> None:
    """Rumble both handles as a strong rumble in a game, until stop_rumble."""
    rumble(root, rumble_report(PULSE_MAGNITUDE))


def stop_rumble(root: Path) -> None:
    rumble(root, rumble_report(0))


def read_driver_strength(root: Path) -> tuple[int, int] | None:
    """The strength the driver last took for the left and right handle.

    The MCU itself cannot be asked; after sleep it is back at 100 whatever the driver says.
    """
    for attribute in sorted((root / DRIVER_STRENGTH).glob("*/vibration_intensity")):
        text = read_text(attribute)
        if text is None:
            continue
        match text.split():
            case [left, right] if left.isdigit() and right.isdigit():
                return int(left), int(right)
            case _:
                return None
    return None
