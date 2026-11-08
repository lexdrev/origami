# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Speaker sound: louder without crackle, wider stereo and clearer voices.

A PipeWire filter chain sits in front of the speaker sink as a smart filter, in a pipewire process
of its own that runs as the session user. Each setting is a constant smoothed by a 15 Hz lowpass
and multiplied into the sound, so a change goes in live through set-param without a click:
PipeWire 1.6's ramp node clamps its controls to 0. The speaker protection is an 8-band limiter
(LSP's multiband compressor) with each console's own thresholds, the ones ASUS tuned its speakers
with on Windows, and a limiter at -1 dBFS after it.

Width adds the side of the stereo above 250 Hz but not in the voice band, and a cut above 250 Hz
keeps the loudness. Voices lift the centre at 2 kHz and lower the sides there, the sides only while
the centre leads them, so a sound on one side keeps its place.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from origami.jsonio import JsonValue, expect_bool

NODE = "origami_sound"
"""Name of the filter's nodes: effect_input.origami_sound in front, effect_output.origami_sound."""
VOLUME_STEPS_DB = (0, 4, 6)
"""The volume steps: the speakers as the system has them, and ASUS's two louder ones."""


class Width(StrEnum):
    OFF = "off"
    MODERATE = "moderate"
    STRONG = "strong"


@dataclass(frozen=True, slots=True)
class Sound:
    """What the user chose on the Sound screen; the defaults are its first values."""

    enabled: bool = True
    volume_db: int = 4
    width: Width = Width.MODERATE
    voices: bool = True

    @classmethod
    def from_json(cls, value: object) -> Sound:
        """Parse sound settings sent by the frontend or saved; raise ValueError on bad input."""
        if not isinstance(value, dict):
            raise ValueError("sound must be an object")
        data = cast("dict[str, object]", value)
        defaults = cls()
        volume = data.get("volume_db", defaults.volume_db)
        if isinstance(volume, bool) or volume not in VOLUME_STEPS_DB:
            raise ValueError(f"volume_db must be one of {VOLUME_STEPS_DB}")
        return cls(
            enabled=expect_bool("enabled", data.get("enabled", defaults.enabled)),
            volume_db=cast("int", volume),
            width=Width(data.get("width", defaults.width)),
            voices=expect_bool("voices", data.get("voices", defaults.voices)),
        )

    def to_json(self) -> dict[str, JsonValue]:
        return {
            "enabled": self.enabled,
            "volume_db": self.volume_db,
            "width": self.width.value,
            "voices": self.voices,
        }


@dataclass(frozen=True, slots=True)
class Zone:
    """A band of the speaker protection: up to its crossover, limited above its threshold."""

    up_to_hz: float | None
    """The crossover to the next band; None for the last band."""
    threshold_db: float


XBOX_ALLY = (Zone(932.8, 0.0), Zone(1163.5, -15.0), Zone(None, 0.0))
"""ROG Xbox Ally X and ROG Xbox Ally: one tuning, the band around 1 kHz held 15 dB lower."""
XBOX_ALLY_X20 = (
    Zone(81.4, -10.375),
    Zone(181.6, -15.125),
    Zone(277.0, -13.375),
    Zone(392.2, -6.0),
    Zone(554.7, -9.0),
    Zone(932.8, -6.0),
    Zone(1163.5, -15.0),
    Zone(None, 0.0),
)
"""ROG Xbox Ally X20: its speakers need the whole low and middle range held, up to 1.2 kHz."""
SPEAKER_ZONES: Mapping[str, tuple[Zone, ...]] = {
    "RC73XA": XBOX_ALLY,
    "RC73YA": XBOX_ALLY,
    "RC74XA": XBOX_ALLY_X20,
}
"""Consoles whose speakers ORIGAMI processes, by board. The ROG Ally and ROG Ally X have
equalisers of their own in ASUS's tuning and wait for owners to check them."""

LSP_BANDS = 8
LSP_FLOOR_DB = -60.0
"""The deepest threshold an LSP compressor band takes."""
WIDTHS: Mapping[Width, tuple[float, float]] = {
    Width.OFF: (0.0, 0.0),
    Width.MODERATE: (1.0, 0.091),
    Width.STRONG: (1.6, 0.156),
}
"""Side gain and the cut above 250 Hz that keeps the loudness, measured on game sound."""
VOICE_LIFT = 0.995
"""The centre at 2 kHz: +6 dB."""
SIDE_CUT = 0.75
"""The sides at 2 kHz while the centre leads them: down to -12 dB."""


def controls(sound: Sound) -> dict[str, float]:
    """The filter's live controls for these settings, by "node:port"."""
    side, cut = WIDTHS[sound.width]
    lift, duck = (VOICE_LIFT, SIDE_CUT) if sound.voices else (0.0, 0.0)
    return {
        "dc_g:Add": round(10 ** (sound.volume_db / 20), 9),
        "dc_k:Add": side,
        "dc_w:Add": cut,
        "dc_d:Add": lift,
        "dc_c:Add": duck,
    }


def set_param_props(values: Mapping[str, float]) -> str:
    """The Props argument of pw-cli set-param that sets these controls."""
    pairs = " ".join(f'"{name}" {_number(value)}' for name, value in values.items())
    return f"{{ params = [ {pairs} ] }}"


def _db(value: float) -> float:
    return 10 ** (value / 20)


def regulator_controls(zones: tuple[Zone, ...]) -> dict[str, float]:
    """LSP multiband compressor controls for the protection bands: hard limiting, 1 ms ahead."""
    if not 1 <= len(zones) <= LSP_BANDS:
        raise ValueError(f"The protection takes 1 to {LSP_BANDS} bands")
    result = {"mode": 1, "g_in": 1, "g_out": 1, "g_dry": _db(-80.01), "g_wet": 1, "envb": 0}
    for band in range(LSP_BANDS):
        on = band < len(zones)
        if band > 0:
            result[f"cbe_{band}"] = 1 if on else 0
            split = zones[band - 1].up_to_hz if on else None
            result[f"sf_{band}"] = split if split is not None else 100.0
        threshold = max(zones[band].threshold_db, LSP_FLOOR_DB) if on else -12.0
        result |= {
            f"ce_{band}": 1 if on else 0,
            f"al_{band}": _db(threshold),
            f"at_{band}": 20,
            f"rrl_{band}": _db(-80.01),
            f"rt_{band}": 50 if on else 100,
            f"cr_{band}": 100 if on else 1,
            f"kn_{band}": _db(-4.5 if on else -6.0),
            f"mk_{band}": 1,
            f"scm_{band}": 0 if on else 1,
            f"sla_{band}": 1 if on else 0,
            f"scp_{band}": 1,
            f"cm_{band}": 0,
            f"bth_{band}": _db(-60.0),
            f"bsa_{band}": 1,
            f"sclc_{band}": 0,
            f"schc_{band}": 0,
            f"sclf_{band}": 10,
            f"schf_{band}": 20000,
        }
    return result


LIMITER = {
    "mode": 0,
    "g_in": 1,
    "g_out": 1,
    "th": _db(-1.0),
    "lk": 1,
    "at": 1,
    "rt": 5,
    "slink": 100,
    "alr": 1,
    "alr_at": 10,
    "alr_rt": 200,
    "knee": _db(6.0),
    "boost": 0,
}
"""LSP limiter: peaks no higher than -1 dBFS, with automatic level regulation."""
LSP = "http://lsp-plug.in/plugins/lv2/"
SMOOTH = {"Freq": 15.0, "Q": 0.5}
"""The lowpass a constant goes through, so a change takes about 50 ms instead of a jump."""


def _number(value: float) -> str:
    return f"{value:.9g}"


class _Graph:
    """Nodes and links of the filter graph, written as PipeWire's configuration has them."""

    def __init__(self, start: Mapping[str, float]) -> None:
        self.start = start
        self.nodes: list[str] = []
        self.links: list[str] = []

    def node(self, label: str, name: str, control: Mapping[str, float] | None = None) -> None:
        values = "".join(f' "{port}" = {_number(value)}' for port, value in (control or {}).items())
        extra = f" control = {{{values} }}" if values else ""
        self.nodes.append(f'{{ type = "builtin" label = "{label}" name = "{name}"{extra} }}')

    def plugin(self, name: str, plugin: str, control: Mapping[str, float]) -> None:
        values = " ".join(f"{port} = {_number(value)}" for port, value in control.items())
        head = f'type = "lv2" name = "{name}" plugin = "{LSP}{plugin}"'
        self.nodes.append(f"{{ {head} control = {{ {values} }} }}")

    def link(self, source: str, sink: str) -> None:
        self.links.append(f'{{ output = "{source}" input = "{sink}" }}')

    def constant(self, name: str, smoothed: str) -> None:
        """A constant signal (any input times 0, plus the value), then smoothed."""
        self.node("linear", name, {"Mult": 0.0, "Add": self.start[f"{name}:Add"]})
        self.node("bq_lowpass", smoothed, SMOOTH)
        self.link("w_l:Out", f"{name}:In")
        self.link(f"{name}:Out", f"{smoothed}:In")


def _inputs(graph: _Graph) -> None:
    """L and R, and the side S = (L - R) / 2."""
    graph.node("copy", "w_l")
    graph.node("copy", "w_r")
    graph.node("invert", "w_inv_r")
    graph.node("mixer", "w_side", {"Gain 1": 0.5, "Gain 2": 0.5})
    graph.link("w_r:Out", "w_inv_r:In")
    graph.link("w_l:Out", "w_side:In 1")
    graph.link("w_inv_r:Out", "w_side:In 2")


def _width(graph: _Graph) -> None:
    """The side above 250 Hz and outside the voice band, times dc_k, into L and out of R."""
    graph.node("bq_highpass", "w_hp", {"Freq": 250.0, "Q": 0.707})
    graph.node("bq_peaking", "w_dip", {"Freq": 1800.0, "Q": 0.5, "Gain": -20.0})
    graph.constant("dc_k", "s_k")
    graph.node("mult", "w_side_k")
    graph.node("invert", "w_inv_s")
    graph.link("w_side:Out", "w_hp:In")
    graph.link("w_hp:Out", "w_dip:In")
    graph.link("w_dip:Out", "w_side_k:In 1")
    graph.link("s_k:Out", "w_side_k:In 2")
    graph.link("w_side_k:Out", "w_inv_s:In")
    # The sums: L or R, the width, the voice lift and the side cut.
    gains = {"Gain 1": 1.0, "Gain 2": 1.0, "Gain 3": 1.0, "Gain 4": 1.0}
    graph.node("mixer", "w_out_l", gains)
    graph.node("mixer", "w_out_r", gains)
    graph.link("w_l:Out", "w_out_l:In 1")
    graph.link("w_side_k:Out", "w_out_l:In 2")
    graph.link("w_r:Out", "w_out_r:In 1")
    graph.link("w_inv_s:Out", "w_out_r:In 2")


def _voices(graph: _Graph) -> None:
    """The mid (L + R) / 2 at 2 kHz, times dc_d, into both."""
    graph.node("mixer", "v_mid", {"Gain 1": 0.5, "Gain 2": 0.5})
    graph.node("bq_bandpass", "v_bp", {"Freq": 2000.0, "Q": 1.0})
    graph.constant("dc_d", "s_d")
    graph.node("mult", "v_amt")
    graph.link("w_l:Out", "v_mid:In 1")
    graph.link("w_r:Out", "v_mid:In 2")
    graph.link("v_mid:Out", "v_bp:In")
    graph.link("v_bp:Out", "v_amt:In 1")
    graph.link("s_d:Out", "v_amt:In 2")
    graph.link("v_amt:Out", "w_out_l:In 3")
    graph.link("v_amt:Out", "w_out_r:In 3")


def _side_cut(graph: _Graph) -> None:
    """The side at 2 kHz, cut by dc_c times how far the centre leads it there.

    Envelopes of both (abs, a 5 Hz lowpass, never 0 for log), their ratio as 10 * log10, and 3 to 6
    of it (an amplitude lead of 6 to 12 dB) mapped onto 0 to 1.
    """
    graph.node("bq_bandpass", "v_sbp", {"Freq": 2000.0, "Q": 1.0})
    graph.constant("dc_c", "s_c")
    graph.link("w_side:Out", "v_sbp:In")
    for part, source in (("m", "v_bp"), ("s", "v_sbp")):
        graph.node("abs", f"e_abs_{part}")
        graph.node("bq_lowpass", f"e_lp_{part}", {"Freq": 5.0, "Q": 0.5})
        graph.node("linear", f"e_eps_{part}", {"Mult": 1.0, "Add": 0.00001})
        graph.node("log", f"e_log_{part}", {"Base": 10.0, "M1": 1.0, "M2": 10.0})
        graph.link(f"{source}:Out", f"e_abs_{part}:In")
        graph.link(f"e_abs_{part}:Out", f"e_lp_{part}:In")
        graph.link(f"e_lp_{part}:Out", f"e_eps_{part}:In")
        graph.link(f"e_eps_{part}:Out", f"e_log_{part}:In")
    graph.node("invert", "e_inv_s")
    graph.node("mixer", "e_ratio", {"Gain 1": 1.0, "Gain 2": 1.0})
    graph.node("linear", "e_ramp", {"Mult": 1 / 3, "Add": -1.0})
    graph.node("clamp", "e_clamp", {"Min": 0.0, "Max": 1.0})
    graph.node("mult", "c_t")
    graph.node("mult", "v_sc")
    graph.node("invert", "v_sc_inv")
    graph.link("e_log_s:Out", "e_inv_s:In")
    graph.link("e_log_m:Out", "e_ratio:In 1")
    graph.link("e_inv_s:Out", "e_ratio:In 2")
    graph.link("e_ratio:Out", "e_ramp:In")
    graph.link("e_ramp:Out", "e_clamp:In")
    graph.link("e_clamp:Out", "c_t:In 1")
    graph.link("s_c:Out", "c_t:In 2")
    graph.link("v_sbp:Out", "v_sc:In 1")
    graph.link("c_t:Out", "v_sc:In 2")
    graph.link("v_sc:Out", "v_sc_inv:In")
    graph.link("v_sc_inv:Out", "w_out_l:In 4")
    graph.link("v_sc:Out", "w_out_r:In 4")


def _loudness(graph: _Graph) -> None:
    """The loudness the width adds, taken off above 250 Hz: y = x - dc_w * HP(x)."""
    graph.constant("dc_w", "s_w")
    for side in ("l", "r"):
        graph.node("bq_highpass", f"c_hp_{side}", {"Freq": 250.0, "Q": 0.707})
        graph.node("mult", f"c_m_{side}")
        graph.node("invert", f"c_inv_{side}")
        graph.node("mixer", f"comp_{side}", {"Gain 1": 1.0, "Gain 2": 1.0})
        graph.link(f"w_out_{side}:Out", f"c_hp_{side}:In")
        graph.link(f"c_hp_{side}:Out", f"c_m_{side}:In 1")
        graph.link("s_w:Out", f"c_m_{side}:In 2")
        graph.link(f"c_m_{side}:Out", f"c_inv_{side}:In")
        graph.link(f"w_out_{side}:Out", f"comp_{side}:In 1")
        graph.link(f"c_inv_{side}:Out", f"comp_{side}:In 2")


def _output(graph: _Graph, zones: tuple[Zone, ...]) -> None:
    """Volume (dc_g), then the speaker protection and the limiter."""
    graph.constant("dc_g", "s_g")
    for side in ("l", "r"):
        graph.node("mult", f"g_{side}")
        graph.link(f"comp_{side}:Out", f"g_{side}:In 1")
        graph.link("s_g:Out", f"g_{side}:In 2")
        graph.link(f"g_{side}:Out", f"reg:in_{side}")
        graph.link(f"reg:out_{side}", f"limiter:in_{side}")
    graph.plugin("reg", "mb_compressor_stereo", regulator_controls(zones))
    graph.plugin("limiter", "limiter_stereo", LIMITER)


def _graph(zones: tuple[Zone, ...], start: Mapping[str, float]) -> _Graph:
    graph = _Graph(start)
    _inputs(graph)
    _width(graph)
    _voices(graph)
    _side_cut(graph)
    _loudness(graph)
    _output(graph, zones)
    return graph


def chain_config(zones: tuple[Zone, ...], sink: str, sound: Sound) -> str:
    """The pipewire -c configuration of the filter in front of the speaker sink `sink`."""
    graph = _graph(zones, controls(sound))
    nodes, links = graph.nodes, graph.links
    indent = "\n            "
    target = json.dumps(sink)
    return f"""# ORIGAMI speaker sound, written by ORIGAMI each time it starts the filter.
context.properties = {{ log.level = 2 }}
context.spa-libs = {{
    audio.convert.* = audioconvert/libspa-audioconvert
    support.* = support/libspa-support
}}
context.modules = [
    {{ name = libpipewire-module-rt args = {{ }} flags = [ ifexists nofail ] }}
    {{ name = libpipewire-module-protocol-native }}
    {{ name = libpipewire-module-client-node }}
    {{ name = libpipewire-module-adapter }}
    {{ name = libpipewire-module-filter-chain
        args = {{
            node.description = "ORIGAMI sound"
            media.name = "ORIGAMI sound"
            filter.graph = {{
                nodes = [{indent}{indent.join(nodes)}
                ]
                links = [{indent}{indent.join(links)}
                ]
                inputs = [ "w_l:In" "w_r:In" ]
                outputs = [ "limiter:out_l" "limiter:out_r" ]
            }}
            audio.channels = 2
            audio.position = [ FL FR ]
            capture.props = {{
                node.name = "effect_input.{NODE}"
                media.class = Audio/Sink
                node.link-group = "{NODE}"
                filter.smart = true
                filter.smart.name = "{NODE}"
                filter.smart.target = {{ node.name = {target} }}
                priority.session = -1
            }}
            playback.props = {{
                node.name = "effect_output.{NODE}"
                node.passive = true
                node.link-group = "{NODE}"
            }}
        }}
    }}
]
"""


@dataclass(frozen=True, slots=True)
class Speakers:
    """The sink the speakers play through, from pw-dump."""

    sink: str
    playing: bool
    """The speakers play now, not headphones on the same sink."""


HDA_SPEAKER_ROUTE = "analog-output-speaker"
"""The speaker port of an HDA codec's analog sink; its headphones are another port of that sink."""


def find_speakers(objects: list[JsonValue]) -> Speakers | None:
    """The speaker sink in pw-dump's objects, or None while there is none.

    A SoundWire console (the X20) has a sink of its own for the speakers (UCM device Speaker), so
    headphones go to another sink. On an HDA console (the Xbox Ally X) the speakers and the jack are
    two routes of one sink, and the device's active route tells which plays.
    """
    devices: dict[int, dict[str, JsonValue]] = {}
    sinks: list[tuple[str, int | None]] = []
    for item in objects:
        if not isinstance(item, dict):
            continue
        kind, info = item.get("type"), item.get("info")
        if not isinstance(kind, str) or not isinstance(info, dict):
            continue
        props = info.get("props")
        props = props if isinstance(props, dict) else {}
        if kind.endswith(":Device") and isinstance(item.get("id"), int):
            devices[cast("int", item["id"])] = info
        elif kind.endswith(":Node") and props.get("media.class") == "Audio/Sink":
            name, device = props.get("node.name"), props.get("device.id")
            if isinstance(name, str) and name.startswith("alsa_output."):
                sinks.append((name, device if isinstance(device, int) else None))
    for name, _ in sinks:
        if "Speaker" in name:
            return Speakers(name, playing=True)
    for name, device in sinks:
        params = devices.get(device, {}).get("params") if device is not None else None
        if not isinstance(params, dict):
            continue
        if HDA_SPEAKER_ROUTE in _routes(params.get("EnumRoute")):
            return Speakers(name, playing=HDA_SPEAKER_ROUTE in _routes(params.get("Route")))
    return None


def _routes(value: JsonValue | None) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {
        name
        for route in value
        if isinstance(route, dict)
        and route.get("direction") == "Output"
        and isinstance(name := route.get("name"), str)
    }


def filter_node(objects: list[JsonValue]) -> int | None:
    """The id of ORIGAMI's filter input node, while the filter runs."""
    for item in objects:
        if not isinstance(item, dict) or not str(item.get("type", "")).endswith(":Node"):
            continue
        info = item.get("info")
        props = info.get("props") if isinstance(info, dict) else None
        node_id = item.get("id")
        if isinstance(props, dict) and props.get("node.name") == f"effect_input.{NODE}":
            return node_id if isinstance(node_id, int) else None
    return None


def parse_dump(text: str) -> list[JsonValue]:
    """pw-dump's output: a JSON list of objects; raise ValueError otherwise."""
    data = cast("JsonValue", json.loads(text))
    if not isinstance(data, list):
        raise ValueError("pw-dump did not print a list")
    return data
