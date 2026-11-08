# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import json
import re
from collections.abc import Mapping
from pathlib import Path

import pytest

from origami import clock
from origami.blocks import Context
from origami.blocks import sound as sound_block
from origami.blocks.sound import CONFIG, UNIT, SoundBlock
from origami.decky_plugins import Conflicts
from origami.journal import ChangeJournal
from origami.jsonio import JsonValue
from origami.proc import CommandError
from origami.settings import Settings
from origami.sound import (
    NODE,
    SPEAKER_ZONES,
    XBOX_ALLY,
    XBOX_ALLY_X20,
    Sound,
    Speakers,
    Width,
    Zone,
    chain_config,
    controls,
    filter_node,
    find_speakers,
    regulator_controls,
    set_param_props,
)

HDA_SINK = "alsa_output.pci-0000_64_00.6.analog-stereo"
X20_SINK = "alsa_output.pci-0000_c4_00.5-platform-amd_sdw.HiFi__Speaker__sink"


def hda_dump(
    route: str = "analog-output-speaker", *, filter_running: bool = False
) -> list[JsonValue]:
    """pw-dump's objects as on the Xbox Ally X: the speakers and the jack are routes of one sink."""
    objects: list[JsonValue] = [
        {
            "id": 44,
            "type": "PipeWire:Interface:Device",
            "info": {
                "props": {"device.api": "alsa", "device.name": "alsa_card.pci-0000_64_00.6"},
                "params": {
                    "EnumRoute": [
                        {"direction": "Input", "name": "analog-input-internal-mic"},
                        {"direction": "Output", "name": "analog-output-speaker"},
                        {"direction": "Output", "name": "analog-output-headphones"},
                    ],
                    "Route": [
                        {"direction": "Input", "name": "analog-input-internal-mic"},
                        {"direction": "Output", "name": route},
                    ],
                },
            },
        },
        {
            "id": 52,
            "type": "PipeWire:Interface:Node",
            "info": {
                "props": {"media.class": "Audio/Sink", "node.name": HDA_SINK, "device.id": 44}
            },
        },
    ]
    if filter_running:
        objects.append(
            {
                "id": 90,
                "type": "PipeWire:Interface:Node",
                "info": {
                    "props": {"media.class": "Audio/Sink", "node.name": f"effect_input.{NODE}"}
                },
            }
        )
    return objects


def test_sound_settings_parse_and_keep_their_defaults() -> None:
    assert Sound.from_json({}) == Sound()
    sound = Sound.from_json({"enabled": False, "volume_db": 6, "width": "strong", "voices": False})
    assert sound == Sound(enabled=False, volume_db=6, width=Width.STRONG, voices=False)
    assert Sound.from_json(sound.to_json()) == sound


@pytest.mark.parametrize(
    "value",
    [
        {"volume_db": 5},
        {"volume_db": True},
        {"volume_db": "4"},
        {"width": "wide"},
        {"voices": 1},
        [],
    ],
)
def test_sound_settings_refuse_bad_values(value: object) -> None:
    with pytest.raises(ValueError):
        Sound.from_json(value)


def test_settings_keep_sound_and_the_clock_fix() -> None:
    settings = Settings().updated({"sound": {"volume_db": 0}, "clock_fix": True})
    assert settings.sound == Sound(volume_db=0)
    assert settings.clock_fix is True
    saved = settings.to_json()
    del saved["version"]
    assert Settings().updated(saved) == settings
    restored = settings.restored()
    assert restored.sound is None
    assert restored.clock_fix is None


def test_controls_follow_the_settings() -> None:
    assert controls(Sound(volume_db=0, width=Width.OFF, voices=False)) == {
        "dc_g:Add": 1.0,
        "dc_k:Add": 0.0,
        "dc_w:Add": 0.0,
        "dc_d:Add": 0.0,
        "dc_c:Add": 0.0,
    }
    values = controls(Sound(volume_db=6, width=Width.STRONG, voices=True))
    assert values["dc_g:Add"] == pytest.approx(10 ** (6 / 20))
    assert values["dc_k:Add"] > controls(Sound(width=Width.MODERATE))["dc_k:Add"]
    assert values["dc_d:Add"] > 0
    assert values["dc_c:Add"] > 0


def test_set_param_props() -> None:
    assert set_param_props({"dc_g:Add": 1.584893192, "dc_k:Add": 0.0}) == (
        '{ params = [ "dc_g:Add" 1.58489319 "dc_k:Add" 0 ] }'
    )


def test_the_xbox_ally_protection_holds_the_band_around_1_khz() -> None:
    values = regulator_controls(XBOX_ALLY)
    assert [values[f"ce_{band}"] for band in range(8)] == [1, 1, 1, 0, 0, 0, 0, 0]
    assert [values[f"cbe_{band}"] for band in range(1, 8)] == [1, 1, 0, 0, 0, 0, 0]
    assert values["sf_1"] == 932.8
    assert values["sf_2"] == 1163.5
    assert values["al_0"] == pytest.approx(1.0)
    assert values["al_1"] == pytest.approx(0.177827941)
    assert values["cr_1"] == 100
    assert values["kn_1"] == pytest.approx(0.5956621435)
    assert values["sla_1"] == 1


def test_the_x20_protection_has_eight_bands() -> None:
    values = regulator_controls(XBOX_ALLY_X20)
    assert all(values[f"ce_{band}"] == 1 for band in range(8))
    assert [values[f"sf_{band}"] for band in range(1, 8)] == [
        zone.up_to_hz for zone in XBOX_ALLY_X20[:-1]
    ]


def test_the_protection_takes_at_most_eight_bands() -> None:
    with pytest.raises(ValueError):
        regulator_controls(tuple(Zone(float(100 * index), -6.0) for index in range(9)))


def test_the_supported_consoles() -> None:
    assert set(SPEAKER_ZONES) == {"RC73XA", "RC73YA", "RC74XA"}


@pytest.mark.parametrize("zones", [XBOX_ALLY, XBOX_ALLY_X20])
def test_chain_config_links_only_its_own_nodes(zones: tuple[Zone, ...]) -> None:
    text = chain_config(zones, HDA_SINK, Sound())
    names = set(re.findall(r'name = "([a-z_0-9]+)"', text))
    for endpoint in re.findall(r'(?:output|input) = "([a-z_0-9]+):', text):
        assert endpoint in names
    assert f'filter.smart.target = {{ node.name = "{HDA_SINK}" }}' in text
    assert f'node.name = "effect_input.{NODE}"' in text
    assert '"Add" = 1.58489319' in text
    assert text.count("{") == text.count("}")


def test_the_speakers_of_an_hda_console() -> None:
    assert find_speakers(hda_dump()) == Speakers(HDA_SINK, playing=True)
    assert find_speakers(hda_dump("analog-output-headphones")) == Speakers(HDA_SINK, playing=False)


def test_the_speakers_of_a_soundwire_console_have_their_own_sink() -> None:
    objects: list[JsonValue] = [
        {
            "id": 61,
            "type": "PipeWire:Interface:Node",
            "info": {"props": {"media.class": "Audio/Sink", "node.name": X20_SINK}},
        },
        {
            "id": 62,
            "type": "PipeWire:Interface:Node",
            "info": {
                "props": {
                    "media.class": "Audio/Sink",
                    "node.name": X20_SINK.replace("Speaker", "Headphones"),
                }
            },
        },
    ]
    assert find_speakers(objects) == Speakers(X20_SINK, playing=True)


def test_no_speakers_without_a_speaker_sink() -> None:
    assert find_speakers([]) is None
    assert find_speakers(hda_dump()[1:]) is None


def test_the_filter_node() -> None:
    assert filter_node(hda_dump()) is None
    assert filter_node(hda_dump(filter_running=True)) == 90


def test_local_rtc(tmp_path: Path) -> None:
    assert not clock.local_rtc(tmp_path)
    (tmp_path / "etc").mkdir()
    (tmp_path / "etc/adjtime").write_text("0.0 1 0.0\n1\nUTC\n", encoding="utf-8")
    assert not clock.local_rtc(tmp_path)
    (tmp_path / "etc/adjtime").write_text("0.0 1 0.0\n1\nLOCAL\n", encoding="utf-8")
    assert clock.local_rtc(tmp_path)


def test_the_crackle_needs_a_local_rtc_a_zone_and_chrony(tmp_path: Path) -> None:
    (tmp_path / "etc").mkdir()
    (tmp_path / "etc/adjtime").write_text("0.0 1 0.0\n1\nLOCAL\n", encoding="utf-8")
    assert not clock.crackles_after_sleep(tmp_path, offset_seconds=3600)
    (tmp_path / "usr/bin").mkdir(parents=True)
    (tmp_path / "usr/bin/chronyc").touch()
    assert clock.crackles_after_sleep(tmp_path, offset_seconds=3600)
    assert not clock.crackles_after_sleep(tmp_path, offset_seconds=0)


class FakeSession:
    """The session user's commands: PipeWire's objects, and the filter's service."""

    def __init__(self) -> None:
        self.route = "analog-output-speaker"
        self.running = False
        self.calls: list[tuple[str, ...]] = []
        self.users: list[tuple[int, int] | None] = []

    async def __call__(
        self, *args: str, user: tuple[int, int] | None = None, env: Mapping[str, str] | None = None
    ) -> str:
        assert env is not None and env["XDG_RUNTIME_DIR"].startswith("/run/user/")
        self.users.append(user)
        if args[0] == "pw-dump":
            return json.dumps(hda_dump(self.route, filter_running=self.running))
        self.calls.append(args)
        if args[0] == "systemd-run":
            self.running = True
        elif args[:3] == ("systemctl", "--user", "stop"):
            if not self.running:
                # systemd collects the stopped service, and stopping what is not there fails so.
                raise CommandError(
                    "systemctl exited with 5: Unit origami-sound.service not loaded.", 5
                )
            self.running = False
        return ""


def no_conflicts(sound: str | None = None) -> Conflicts:
    return Conflicts(
        lighting=None,
        saturation=None,
        vibration=None,
        triggers=None,
        power=None,
        boost=None,
        fans=None,
        sound=sound,
    )


def make_block(
    tmp_path: Path, session: FakeSession, owner: list[str | None], board: str = "RC73XA"
) -> SoundBlock:
    socket = tmp_path / "run/user/1000/pipewire-0"
    socket.parent.mkdir(parents=True)
    socket.touch()

    async def conflicts() -> Conflicts:
        return no_conflicts(owner[0])

    context = Context(tmp_path, ChangeJournal(tmp_path / "changes.json"), conflicts)
    return SoundBlock(context, lv2_dir=Path("/plugin/bin/lv2"), board=lambda: board, runner=session)


@pytest.fixture(autouse=True)
def no_detached_programs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    started: list[tuple[str, ...]] = []

    def start(*args: str, **_: object) -> None:
        started.append(args)

    monkeypatch.setattr(sound_block, "start_detached", start)
    return started


def test_the_filter_starts_changes_live_and_stops(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    session = FakeSession()
    owner: list[str | None] = [None]
    block = make_block(tmp_path, session, owner)

    async def scenario() -> None:
        await block.follow(Settings(sound=Sound()))
        config = tmp_path / "run/user/1000" / CONFIG
        assert config.exists()
        assert HDA_SINK in config.read_text(encoding="utf-8")
        assert session.calls[-1][:3] == ("systemd-run", "--user", f"--unit={UNIT}")
        assert "--setenv=LV2_PATH=/plugin/bin/lv2" in session.calls[-1]
        # A change goes into the running filter, only what changed.
        await block.follow(Settings(sound=Sound(volume_db=6)))
        assert session.calls[-1] == (
            "pw-cli",
            "set-param",
            "90",
            "Props",
            '{ params = [ "dc_g:Add" 1.99526231 ] }',
        )
        # Headphones on the speakers' sink stop it, the speakers start it again.
        session.route = "analog-output-headphones"
        await block.follow(Settings(sound=Sound(volume_db=6)))
        assert session.calls[-1] == ("systemctl", "--user", "stop", UNIT)
        session.route = "analog-output-speaker"
        await block.follow(Settings(sound=Sound(volume_db=6)))
        assert session.calls[-1][0] == "systemd-run"
        # Switched off, it stops; another plugin's filter keeps it stopped.
        await block.follow(Settings(sound=Sound(enabled=False)))
        assert session.calls[-1] == ("systemctl", "--user", "stop", UNIT)
        owner[0] = "Sound Plugin"
        await block.follow(Settings(sound=Sound()))
        assert not session.running
        block.stop()
        await asyncio.sleep(0)

    asyncio.run(scenario())
    assert set(session.users) == {(tmp_path.stat().st_uid, tmp_path.stat().st_gid)}
    # Stopping before the first start finds no service, which is no failure.
    assert "not stopped" not in caplog.text


def test_removing_origami_stops_the_filter_and_removes_its_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stopped: list[tuple[str, ...]] = []

    def run_blocking(*args: str, **_: object) -> str:
        stopped.append(args)
        return ""

    monkeypatch.setattr(sound_block, "run_blocking", run_blocking)
    block = make_block(tmp_path, FakeSession(), [None])
    config = tmp_path / "run/user/1000" / CONFIG
    config.write_text("context.properties = {}\n", encoding="utf-8")

    block.give_back()

    assert stopped == [("systemctl", "--user", "stop", UNIT)]
    assert not config.exists()


def test_nothing_runs_on_a_console_without_its_protection(tmp_path: Path) -> None:
    session = FakeSession()
    block = make_block(tmp_path, session, [None], board="RC71L")

    async def scenario() -> None:
        await block.follow(Settings(sound=Sound()))
        block.stop()

    asyncio.run(scenario())
    assert session.calls == []
