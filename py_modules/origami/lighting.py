# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Lighting of the stick rings.

The driver's LED class passes only blue on kernel 7.2.9-ogc3 (it clips the packed colour to
255), so ORIGAMI sends the MCU's lighting commands itself. The driver still writes
its cached colour into the MCU on every suspend, and nobody fills that cache, so the rings go
dark after sleep until the lighting is sent again (BUGS.md, B12).
"""

from dataclasses import dataclass, fields
from enum import StrEnum
from pathlib import Path
from typing import cast

from origami.controller import VENDOR_REPORT, configure
from origami.jsonio import JsonValue, expect_bool

YELLOW = 0xFFD200
MAX_COLOR = 0xFFFFFF


class LightMode(StrEnum):
    STATIC = "static"
    BREATHING = "breathing"
    RAINBOW = "rainbow"
    SPIRAL = "spiral"


class Speed(StrEnum):
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"


MIN_BRIGHTNESS = 5
MAX_BRIGHTNESS = 100
LOW_BRIGHTNESS = 35
"""Rainbow and spiral glow at the MCU's low level up to here, at medium up to MEDIUM_BRIGHTNESS."""
MEDIUM_BRIGHTNESS = 70
# Settings saved before the slider (1.0.0) kept one of the MCU's three levels by name.
OLD_LEVELS = {"low": LOW_BRIGHTNESS, "medium": MEDIUM_BRIGHTNESS, "high": MAX_BRIGHTNESS}


@dataclass(frozen=True, slots=True)
class Lighting:
    enabled: bool = True
    """Off keeps the rings dark; the other fields wait for the next time it is on."""
    mode: LightMode = LightMode.SPIRAL
    left: int = YELLOW
    """Colour of the left ring as 0xRRGGBB; rainbow and spiral bring their own colours."""
    right: int = YELLOW
    speed: Speed = Speed.MEDIUM
    brightness: int = MEDIUM_BRIGHTNESS
    """Percent, 5 to 100: smooth for ORIGAMI's colours, three levels for rainbow and spiral."""

    @classmethod
    def from_json(cls, value: object) -> Lighting:
        """Parse lighting sent by the frontend or saved; raise ValueError on bad input.

        Missing keys take their defaults and unknown ones are skipped, so settings written
        by another version still load.
        """
        if not isinstance(value, dict):
            raise ValueError("lighting must be an object")
        data = cast("dict[str, object]", value)
        defaults = cls()
        return cls(
            enabled=expect_bool("enabled", data.get("enabled", defaults.enabled)),
            mode=_member(LightMode, "mode", data.get("mode", defaults.mode)),
            left=_color("left", data.get("left", defaults.left)),
            right=_color("right", data.get("right", defaults.right)),
            speed=_member(Speed, "speed", data.get("speed", defaults.speed)),
            brightness=_brightness(data.get("brightness", defaults.brightness)),
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {field.name: _json(getattr(self, field.name)) for field in fields(self)}


CONTROLLER_LIGHTING = Lighting(mode=LightMode.RAINBOW)
"""What the rings show until anybody sets them: the controller's own rainbow (BUGS.md, B12)."""


def _member[E: StrEnum](kind: type[E], key: str, value: object) -> E:
    try:
        return kind(value)
    except ValueError:
        raise ValueError(f"{key} must be one of: {', '.join(kind)}") from None


def _color(key: str, value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_COLOR:
        return value
    raise ValueError(f"{key} must be a colour from 0 to 0xFFFFFF")


def _brightness(value: object) -> int:
    if isinstance(value, str) and value in OLD_LEVELS:
        return OLD_LEVELS[value]
    if (
        isinstance(value, int)
        and not isinstance(value, bool)
        and MIN_BRIGHTNESS <= value <= MAX_BRIGHTNESS
    ):
        return value
    raise ValueError(f"brightness must be a percent from {MIN_BRIGHTNESS} to {MAX_BRIGHTNESS}")


def _json(value: object) -> JsonValue:
    return value.value if isinstance(value, StrEnum) else cast("JsonValue", value)


# MCU commands, as the hid-asus-ally driver sends them:
#   5a b3 <zone> <mode> <r g b> <speed> <direction> 00 <r g b>   mode and colours of a zone
#   5a b4 / 5a b5                                                apply / store the modes sent
#   5a ba c5 c4 <0-3>                                            brightness
# Zone 0 is both rings; 1 and 2 are the halves of the left ring, 3 and 4 of the right one.
# The second colour is where breathing fades to: black here. Brightness 0 does not keep the
# rings dark (they light up again when the sticks are touched), so off is static black, as the
# driver itself sets before sleep. Levels above 3 put the rings out as well (checked 2026-11-05).
#
# Three levels are all the MCU has, and rainbow and spiral hardly heed the colour sent with them,
# so those two only get the levels. A colour of ORIGAMI's own dims smoothly instead: the MCU
# stays at its top level and gets the colour scaled down, as the driver's LED class does it.
MODE = 0xB3
APPLY = bytes([VENDOR_REPORT, 0xB4])
STORE = bytes([VENDOR_REPORT, 0xB5])
BRIGHTNESS = bytes([VENDOR_REPORT, 0xBA, 0xC5, 0xC4])
ALL_ZONES = 0
LEFT_ZONES = (1, 2)
RIGHT_ZONES = (3, 4)

MODE_CODES = {
    LightMode.STATIC: 0,
    LightMode.BREATHING: 1,
    LightMode.RAINBOW: 2,
    LightMode.SPIRAL: 3,
}
SPEED_CODES = {Speed.SLOW: 0xE1, Speed.MEDIUM: 0xEB, Speed.FAST: 0xF5}
TOP_LEVEL = 3
DIM_CURVE = 1.3
"""The slider's 5% gives 2% of the colour: the dimmest checked on the console still in its hue."""


def mcu_level(brightness: int) -> int:
    """The MCU's level, 1 to 3, that rainbow and spiral show for the brightness."""
    if brightness <= LOW_BRIGHTNESS:
        return 1
    return 2 if brightness <= MEDIUM_BRIGHTNESS else TOP_LEVEL


def dimmed(colour: int, brightness: int) -> int:
    """The colour scaled for the brightness; a channel that is on keeps at least 1, and the hue."""
    share = (brightness / MAX_BRIGHTNESS) ** DIM_CURVE
    channels = [(colour >> shift) & 0xFF for shift in (16, 8, 0)]
    red, green, blue = (max(1, round(value * share)) if value else 0 for value in channels)
    return (red << 16) | (green << 8) | blue


def lighting_reports(lighting: Lighting) -> list[bytes]:
    """The MCU commands for the lighting, in the order the driver sends them."""
    if not lighting.enabled:
        dark = Lighting(mode=LightMode.STATIC, left=0, right=0)
        return [_mode_report(ALL_ZONES, 0, dark), APPLY, STORE]
    own_colours = lighting.mode in (LightMode.RAINBOW, LightMode.SPIRAL)
    if own_colours:
        level, left, right = mcu_level(lighting.brightness), lighting.left, lighting.right
    else:
        level = TOP_LEVEL
        left = dimmed(lighting.left, lighting.brightness)
        right = dimmed(lighting.right, lighting.brightness)
    if own_colours or left == right:
        zones = [(ALL_ZONES, left)]
    else:
        zones = [(zone, left) for zone in LEFT_ZONES]
        zones += [(zone, right) for zone in RIGHT_ZONES]
    reports = [BRIGHTNESS + bytes([level])]
    reports += [_mode_report(zone, colour, lighting) for zone, colour in zones]
    return [*reports, APPLY, STORE]


def _mode_report(zone: int, colour: int, lighting: Lighting) -> bytes:
    speed = 0 if lighting.mode is LightMode.STATIC else SPEED_CODES[lighting.speed]
    red, green, blue = (colour >> 16) & 0xFF, (colour >> 8) & 0xFF, colour & 0xFF
    mode = MODE_CODES[lighting.mode]
    return bytes([VENDOR_REPORT, MODE, zone, mode, red, green, blue, speed, 0, 0, 0, 0, 0])


def apply_lighting(root: Path, lighting: Lighting) -> None:
    """Send the lighting to the controller; raise OSError when it cannot be reached."""
    configure(root, lighting_reports(lighting))
