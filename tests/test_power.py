# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from contextlib import aclosing

import pytest

from origami.power import (
    FOREIGN_LIMIT,
    MIN_LOOK_SECONDS,
    POLL_SECONDS,
    QUIET_SECONDS,
    WATCH_LOOK_SECONDS,
    WATCH_SECONDS,
    HeldPower,
    Power,
    PowerKeeper,
    PowerTarget,
    resumes,
)
from origami.tdp import Limits, read_limits, write_limits

from fakes import FakeRoot

ARMOURY = "sys/class/firmware-attributes/asus-armoury/attributes"
CPUFREQ = "sys/devices/system/cpu/cpufreq"
FACTORY = Limits(17, 21, 26)


def test_a_jump_of_the_sleep_gap_is_a_resume() -> None:
    # Gap between the boot-time and monotonic clocks: steady, then 30 s asleep, then steady.
    gaps = iter([5.0, 5.001, 5.002, 35.0, 35.001])

    async def scenario() -> int:
        count = 0
        async with aclosing(resumes(poll_seconds=0, asleep=lambda: next(gaps))) as wakes:
            async for _ in wakes:
                count += 1
                break
        return count

    assert asyncio.run(scenario()) == 1
    assert next(gaps) == 35.001


def test_power_settings_are_parsed_and_checked() -> None:
    assert Power.from_json({"tdp": 25, "headroom": False, "cpu_boost": True}) == Power(
        25, headroom=False, cpu_boost=True
    )
    assert Power.from_json({}) == Power()
    for bad in ({"tdp": 6}, {"tdp": 36}, {"tdp": True}, {"headroom": 1}, {"cpu_boost": "on"}):
        with pytest.raises(ValueError, match=r"tdp|headroom|cpu_boost"):
            Power.from_json(bad)
    assert Power.from_json(Power(20, cpu_boost=False).to_json()) == Power(20, cpu_boost=False)


def test_the_battery_holds_the_tdp_at_25_watts_unless_allowed() -> None:
    target = PowerTarget(Power(30), tdp=True)

    assert target.tdp_for(mains=True) == 30
    assert target.tdp_for(mains=False) == 25
    assert PowerTarget(Power(30), tdp=True, battery_high_tdp=True).tdp_for(mains=False) == 30


class Console:
    """The powered console, the keeper's clocks and helpers to change what it sees."""

    def __init__(self, root: FakeRoot) -> None:
        self.root = root
        self.now = 100.0
        self.asleep = 5.0
        self.keeper = PowerKeeper(root.path, clock=lambda: self.now, asleep=lambda: self.asleep)

    def tick(self, seconds: float = 2.0) -> str | None:
        """Let time pass and the keeper look; return why the CPU's cap is due, if it is."""
        self.now += seconds
        return self.keeper.tick()

    def limits(self) -> Limits | None:
        return read_limits(self.root.path)

    def overwrite(self, limits: Limits) -> None:
        """Someone else writes limits, as Steam through steamos-manager."""
        write_limits(self.root.path, limits)

    def plug(self, *, online: bool) -> None:
        # The driver shows the charger's set, never written since boot: its maximum.
        self.root.write("sys/class/power_supply/AC0/online", int(online))
        self.overwrite(Limits(35, 45, 55) if online else FACTORY)
        self.root.write(f"{ARMOURY}/ppt_pl2_sppt/min_value", 14 if online else 13)

    def profile(self, name: str) -> None:
        self.root.write("sys/class/platform-profile/platform-profile-1/profile", name)

    def power(self, watts: float) -> None:
        self.root.write("sys/class/hwmon/hwmon5/power1_average", int(watts * 1_000_000))

    def boost(self) -> str:
        return (self.root.path / CPUFREQ / "boost").read_text(encoding="utf-8")

    def core(self, khz: int) -> None:
        self.root.write(f"{CPUFREQ}/policy1/scaling_cur_freq", khz)


@pytest.fixture
def console(powered: FakeRoot) -> Console:
    return Console(powered)


@pytest.fixture
def info(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    caplog.set_level("INFO")
    return caplog


def hold(
    console: Console,
    power: Power | None = None,
    *,
    tdp: bool = True,
    battery_high_tdp: bool = False,
    steam_slider: bool = False,
) -> None:
    target = PowerTarget(
        power or Power(), tdp=tdp, battery_high_tdp=battery_high_tdp, steam_slider=steam_slider
    )
    console.keeper.hold(target)


def test_the_limits_are_written_at_once_and_then_only_when_something_changes(
    console: Console, info: pytest.LogCaptureFixture
) -> None:
    hold(console, Power(20))
    console.tick()

    assert console.limits() == Limits(20, 24, 29)
    assert console.keeper.held() == HeldPower(
        Limits(20, 24, 29), battery_capped=False, contested=False
    )
    for _ in range(10):
        console.tick()
    assert info.text.count("TDP 20 / 24 / 29 W written") == 1


def test_after_the_charger_the_limits_go_to_its_set_and_steam_is_answered(
    console: Console,
) -> None:
    hold(console, Power(20))
    console.tick()

    # The kernel reports the charger and the keeper looks at once: the charger's set shows its
    # maximum until written.
    console.plug(online=True)
    console.tick(0.1)
    assert console.limits() == Limits(20, 24, 29)

    # Steam's own write in performance lands up to a few seconds later, and is answered.
    assert console.keeper.next_look() == pytest.approx(WATCH_LOOK_SECONDS)
    console.overwrite(Limits(35, 36, 37))
    console.tick(WATCH_LOOK_SECONDS)
    assert console.limits() == Limits(20, 24, 29)


def test_the_keeper_looks_again_when_a_write_is_due_or_after_a_poll(console: Console) -> None:
    hold(console, Power(20))
    assert console.keeper.next_look() == pytest.approx(MIN_LOOK_SECONDS)

    console.tick()
    assert console.keeper.next_look() == pytest.approx(POLL_SECONDS)

    console.keeper.game_started()
    assert console.keeper.next_look() == pytest.approx(WATCH_LOOK_SECONDS)

    console.tick(WATCH_SECONDS)
    assert console.keeper.next_look() == pytest.approx(POLL_SECONDS)


def test_steam_writing_after_origami_is_answered_at_once_and_not_held_against_it(
    console: Console,
) -> None:
    hold(console, Power(20))
    console.tick()

    # Steam writes its 35 W after ORIGAMI's write (probe 21), every time.
    for online in (False, True) * FOREIGN_LIMIT:
        console.plug(online=not online)
        console.tick(0.1)
        assert console.limits() == Limits(20, 24, 29)
        console.overwrite(Limits(35, 36, 37))
        console.tick(WATCH_LOOK_SECONDS)
        assert console.limits() == Limits(20, 24, 29)
        console.tick(QUIET_SECONDS)

    assert console.keeper.held().contested is False


def test_after_sleep_the_limits_are_written_again(console: Console) -> None:
    hold(console, Power(20))
    console.tick()

    console.asleep += 600
    console.overwrite(FACTORY)
    console.tick(1)
    assert console.limits() == FACTORY

    console.tick(2)
    assert console.limits() == Limits(20, 24, 29)


def test_after_a_profile_change_the_limits_are_written_again(console: Console) -> None:
    hold(console, Power(20))
    console.tick()

    # Steam writes the profile, and its own limits with it; the profile brings back its power.
    console.profile("performance")
    console.overwrite(FACTORY)
    console.tick(1)
    assert console.limits() == FACTORY

    console.tick(2)
    assert console.limits() == Limits(20, 24, 29)


def test_limits_someone_else_writes_are_answered_until_they_keep_coming(
    console: Console,
) -> None:
    hold(console, Power(20))
    console.tick()

    for _ in range(FOREIGN_LIMIT):
        console.overwrite(Limits(35, 36, 37))
        console.tick()
        assert console.limits() == Limits(20, 24, 29)
        assert console.keeper.held().contested is False

    console.overwrite(Limits(35, 36, 37))
    console.tick()

    assert console.limits() == Limits(35, 36, 37)
    assert console.keeper.held().contested is True

    # New settings take the TDP back.
    hold(console, Power(21))
    console.tick()
    assert console.limits() == Limits(21, 25, 30)
    assert console.keeper.held().contested is False


def test_steams_slider_is_answered_at_once_however_often_it_moves(console: Console) -> None:
    hold(console, Power(13), steam_slider=True)
    console.tick()
    assert console.keeper.next_look() == pytest.approx(WATCH_LOOK_SECONDS)

    for watts in (20, 21, 20, 15, 18, 25):
        console.overwrite(Limits(watts, watts + 1, watts + 2))
        console.tick(WATCH_LOOK_SECONDS)
        assert console.limits() == Limits(13, 17, 22)

    assert console.keeper.held().contested is False


def test_a_soc_drawing_more_than_the_boost_limit_for_long_gets_the_limits_again(
    console: Console, info: pytest.LogCaptureFixture
) -> None:
    hold(console, Power(17))
    console.tick()

    # A profile's own power: the limits read back as written, while the SoC draws 30 W.
    console.power(30)
    for _ in range(5):
        console.tick()
    assert "the SoC drew" not in info.text

    console.tick()
    assert "TDP 17 / 21 / 26 W written: the SoC drew 30.0 W" in info.text

    info.clear()
    for _ in range(20):
        console.tick()
    assert "the SoC drew" not in info.text


def test_a_short_boost_over_the_tdp_is_no_reason_to_write(
    console: Console, info: pytest.LogCaptureFixture
) -> None:
    hold(console, Power(17))
    console.tick()

    console.power(22.5)
    for _ in range(20):
        console.tick()

    assert "the SoC drew" not in info.text


def test_a_game_start_brings_three_writes_as_steam_settles_it(
    console: Console, info: pytest.LogCaptureFixture
) -> None:
    hold(console, Power(15))
    console.tick()
    console.keeper.game_started()
    start = console.now

    written: list[float] = []
    for _ in range(12):
        before = info.text.count("game started")
        console.tick(1)
        if info.text.count("game started") > before:
            written.append(console.now - start)

    assert written == [2, 5, 10]


def test_on_the_battery_the_tdp_is_held_at_25_watts(console: Console) -> None:
    hold(console, Power(30))
    console.tick()

    assert console.limits() == Limits(25, 29, 34)
    assert console.keeper.held().battery_capped is True

    console.plug(online=True)
    console.tick(0.1)
    assert console.limits() == Limits(30, 34, 39)
    assert console.keeper.held().battery_capped is False


def test_without_the_tdp_only_the_cpu_is_held(console: Console) -> None:
    hold(console, Power(30, cpu_boost=True), tdp=False)
    console.tick()

    assert console.limits() == FACTORY
    assert console.keeper.held().limits is None
    assert console.boost() == "1\n"


def test_the_boost_is_switched_as_chosen_and_kept(console: Console) -> None:
    hold(console, Power(cpu_boost=True))
    console.tick()
    assert console.boost() == "1\n"

    console.root.write(f"{CPUFREQ}/boost", 0)
    console.tick()
    assert console.boost() == "1\n"


def test_an_unchosen_boost_is_left_as_it_is(console: Console) -> None:
    hold(console)
    console.tick()

    assert console.boost() == "0\n"


def test_cores_running_over_their_cap_get_it_programmed_again(console: Console) -> None:
    hold(console)
    assert console.tick() == "after a change"

    console.core(3_500_000)
    # Not on a single look, and not sooner than five seconds after the last time.
    assert [console.tick() for _ in range(2)] == [None, None]
    assert console.tick() == "a core ran at 3500 MHz over the 2000 MHz cap"

    # Not again right away, even while it still runs over.
    assert [console.tick() for _ in range(2)] == [None, None]
    assert console.tick() == "a core ran at 3500 MHz over the 2000 MHz cap"


def test_after_the_charger_the_cap_is_programmed_while_the_boost_is_off(
    console: Console,
) -> None:
    hold(console)
    console.tick()

    console.plug(online=True)
    assert console.tick(0.5) is None
    assert console.tick(1) == "after a change"


def test_the_cap_is_left_alone_while_the_boost_is_on(console: Console) -> None:
    hold(console, Power(cpu_boost=True))
    console.tick()
    console.core(4_800_000)

    assert [console.tick() for _ in range(10)] == [None] * 10


def test_a_boost_someone_else_switches_on_gets_the_cooling_caps_renewed(
    console: Console, info: pytest.LogCaptureFixture
) -> None:
    console.root.write("sys/class/thermal/cooling_device7/type", "Processor")
    console.root.write("sys/class/thermal/cooling_device7/cur_state", 0)
    renewed = "CPU cooling caps renewed"
    hold(console)
    console.tick()

    # Switched on from OpenGamepadUI after a sleep with it off: the cores stay at 2.0 GHz (B20).
    console.root.write(f"{CPUFREQ}/boost", 1)
    for cpu in range(4):
        console.root.write(f"{CPUFREQ}/policy{cpu}/cpuinfo_max_freq", 5_090_910)
    for _ in range(3):
        console.tick()
    assert info.text.count(renewed) == 1

    # Once more after a resume, and each time the boost goes on again.
    console.asleep += 600
    console.tick()
    assert info.text.count(renewed) == 2

    console.root.write(f"{CPUFREQ}/boost", 0)
    console.tick()
    console.root.write(f"{CPUFREQ}/boost", 1)
    console.tick()
    assert info.text.count(renewed) == 3


def test_cores_at_their_boosted_top_need_no_renewal(
    console: Console, info: pytest.LogCaptureFixture
) -> None:
    console.root.write(f"{CPUFREQ}/boost", 1)
    for cpu in range(4):
        console.root.write(f"{CPUFREQ}/policy{cpu}/cpuinfo_max_freq", 5_090_910)
        console.root.write(f"{CPUFREQ}/policy{cpu}/scaling_max_freq", 5_090_910)
    hold(console)

    console.tick()

    assert "CPU cooling caps renewed" not in info.text


def test_a_refused_write_is_logged_and_the_keeper_goes_on(
    console: Console, caplog: pytest.LogCaptureFixture
) -> None:
    refusing = console.root.path / ARMOURY / "ppt_pl2_sppt" / "current_value"
    refusing.unlink()
    refusing.mkdir()
    hold(console, Power(20))

    console.tick()

    assert "Power settings not held" in caplog.text


def test_nothing_is_held_without_a_target(console: Console) -> None:
    hold(console, Power(30))
    console.keeper.hold(None)
    console.tick()

    assert console.limits() == FACTORY


def test_new_tdp_settings_leave_the_cpu_cap_alone(console: Console) -> None:
    hold(console, Power(17))
    assert console.tick() == "after a change"

    hold(console, Power(25))
    assert console.tick() is None
    assert console.limits() == Limits(25, 29, 34)

    # Off from on, the boost leaves the cores to their cap, which is programmed again.
    hold(console, Power(25, cpu_boost=True))
    console.tick()
    hold(console, Power(25, cpu_boost=False))
    console.tick(0.5)
    assert console.tick(1) == "after a change"
