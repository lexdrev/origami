# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

from itertools import pairwise
from pathlib import Path

import pytest

from origami.fans import (
    BALANCE,
    HOLD_COOLEST,
    HOLD_SLOWEST,
    HOLD_START,
    HOLD_WARMEST,
    ROG_ALLY,
    XBOX_ALLY_X,
    Curve,
    FanCurve,
    Hold,
    curve_on,
    fan_speed,
    give_back,
    hold_curve,
    hottest,
    own_curve,
    write_curve,
)

from fakes import FakeRoot


def curve_device(root: FakeRoot) -> Path:
    """The firmware's curve device as after boot: both fans on the firmware's own curve."""
    return root.hwmon(8, "asus_custom_fan_curve", pwm1_enable=2, pwm2_enable=2)


def read(device: Path, name: str) -> int:
    return int((device / name).read_text(encoding="utf-8"))


def test_the_curve_goes_to_both_fans_and_on_with_full_speed_at_100(fake_root: FakeRoot) -> None:
    device = curve_device(fake_root)

    write_curve(fake_root.path, own_curve((0, 10, 25, 40, 55, 75, 100)))

    for fan in (1, 2):
        temps = [read(device, f"pwm{fan}_auto_point{index}_temp") for index in range(1, 9)]
        speeds = [read(device, f"pwm{fan}_auto_point{index}_pwm") for index in range(1, 9)]
        assert temps == [30, 40, 50, 60, 70, 80, 90, 100]
        assert speeds == [0, 26, 64, 102, 140, 191, 255, 255]
        assert read(device, f"pwm{fan}_enable") == 1
    assert curve_on(fake_root.path)


def test_a_profile_written_switches_the_curve_off_and_giving_back_hands_over(
    fake_root: FakeRoot,
) -> None:
    device = curve_device(fake_root)
    write_curve(fake_root.path, own_curve(BALANCE))

    # asus-wmi switches custom curves off as a platform profile is written.
    fake_root.write(f"sys/class/hwmon/{device.name}/pwm2_enable", 2)
    assert not curve_on(fake_root.path)

    give_back(fake_root.path)
    assert [read(device, "pwm1_enable"), read(device, "pwm2_enable")] == [2, 2]


def test_without_the_curve_device_nothing_is_written(fake_root: FakeRoot) -> None:
    with pytest.raises(OSError, match="asus_custom_fan_curve"):
        write_curve(fake_root.path, own_curve(BALANCE))
    assert not curve_on(fake_root.path)
    give_back(fake_root.path)


@pytest.mark.parametrize(
    ("points", "message"),
    [
        ([0, 10, 25, 40, 55, 75], "7 points"),
        ([0, 10, 25, 40, 55, 75, 101], "percentage"),
        ([0, 10, 25, 40, 55, 75, True], "percentage"),
        ([0, 20, 10, 40, 55, 75, 100], "fall"),
        ([0, 10, 25, 40, 45, 45, 45], "at least at 50%"),
    ],
)
def test_curves_that_fall_or_run_hot_are_refused(points: list[object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        FanCurve.from_json({"enabled": True, "points": points})


def test_a_curve_switched_off_keeps_its_points() -> None:
    curve = FanCurve.from_json({"enabled": False, "points": [20, 30, 45, 60, 75, 90, 100]})

    assert curve == FanCurve(enabled=False, points=(20, 30, 45, 60, 75, 90, 100))
    assert FanCurve.from_json(curve.to_json()) == curve
    assert FanCurve.from_json({}) == FanCurve(enabled=True, points=BALANCE)


def test_a_curve_saved_before_the_hold_follows_its_points() -> None:
    curve = FanCurve.from_json({"enabled": True, "points": list(BALANCE)})

    assert (curve.hold, curve.target) == (False, 60)


def test_a_hold_keeps_the_points_for_the_time_it_is_off() -> None:
    curve = FanCurve.from_json(
        {"points": [20, 30, 45, 60, 75, 90, 100], "hold": True, "target": 55}
    )

    assert curve == FanCurve(points=(20, 30, 45, 60, 75, 90, 100), hold=True, target=55)
    assert FanCurve.from_json(curve.to_json()) == curve


@pytest.mark.parametrize("target", [HOLD_COOLEST - 1, HOLD_WARMEST + 1, 60.5, "60", True, None])
def test_a_target_out_of_reach_is_refused(target: object) -> None:
    with pytest.raises(ValueError, match="target"):
        FanCurve.from_json({"hold": True, "target": target})


def speed_at(curve: Curve, temp: float) -> int:
    """The speed the firmware runs the fans at: that of the last point the SoC has passed."""
    passed = [speed for at, speed in curve if at <= temp]
    return passed[-1] if passed else curve[0][1]


def test_the_curve_runs_the_fans_at_the_level_up_to_the_net_over_the_target() -> None:
    assert hold_curve(60, 40) == (
        (30, 40),
        (64, 40),
        (65, 50),
        (66, 65),
        (67, 80),
        (68, 90),
        (70, 100),
        (100, 100),
    )


@pytest.mark.parametrize("target", range(HOLD_COOLEST, HOLD_WARMEST + 1))
def test_every_hold_curve_is_one_the_firmware_takes_and_keeps_the_soc_cool(target: int) -> None:
    for level in range(HOLD_SLOWEST, 101):
        curve = hold_curve(target, level)

        assert len(curve) == 8
        assert all(earlier < later for (earlier, _), (later, _) in pairwise(curve))
        assert all(earlier <= later for (_, earlier), (_, later) in pairwise(curve))
        # One speed around the target, so the fans do not jump as the temperature swings there.
        assert {speed_at(curve, temp) for temp in range(30, target + 4)} == {level}
        assert speed_at(curve, target + 10) == 100
        assert all(speed_at(curve, temp) >= 50 for temp in range(80, 101))


class Soc:
    """The SoC as measured: a TDP's own span of temperatures, the fans moving it within a minute."""

    def __init__(self, slowest: float, fastest: float) -> None:
        self._slowest, self._fastest = slowest, fastest
        self.temp = slowest

    def run(self, hold: Hold, target: int, looks: int) -> list[int]:
        """The levels the hold asks for, look after look, the firmware following its curve."""
        levels: list[int] = []
        for _ in range(looks):
            level = hold.look(self.temp)
            speed = speed_at(hold_curve(target, level), self.temp)
            share = (speed - HOLD_SLOWEST) / (100 - HOLD_SLOWEST)
            rests_at = self._slowest - (self._slowest - self._fastest) * share
            # A look every 5 s; the SoC goes two thirds of the way in 27 s.
            self.temp += (rests_at - self.temp) * 0.17
            levels.append(level)
        return levels


def test_the_hold_settles_at_the_target_without_swinging() -> None:
    soc, hold = Soc(slowest=61.0, fastest=52.7), Hold(57)

    levels = soc.run(hold, 57, 60)

    assert soc.temp == pytest.approx(57, abs=0.6)
    moves = [after - before for before, after in pairwise(levels)]
    turns = sum(
        1 for before, after in pairwise([move for move in moves if move]) if before * after < 0
    )
    assert turns <= 2
    assert max(levels[-12:]) - min(levels[-12:]) <= 2


def test_a_target_the_fans_cannot_reach_ends_at_full_speed() -> None:
    soc, hold = Soc(slowest=73.0, fastest=65.1), Hold(60)

    levels = soc.run(hold, 60, 40)

    assert levels[-1] == 100
    assert soc.temp == pytest.approx(65.1, abs=0.2)


def test_a_soc_cooler_than_the_target_ends_with_the_fans_at_their_slowest() -> None:
    soc, hold = Soc(slowest=54.0, fastest=46.1), Hold(65)

    levels = soc.run(hold, 65, 40)

    assert levels[-1] == HOLD_SLOWEST
    assert soc.temp == pytest.approx(54.0, abs=0.2)


def test_a_game_starting_on_slow_fans_does_not_swing_them() -> None:
    soc, hold = Soc(slowest=54.0, fastest=46.1), Hold(57)
    soc.run(hold, 57, 30)
    game = Soc(slowest=64.0, fastest=55.5)
    game.temp = soc.temp

    levels = game.run(hold, 57, 60)

    assert game.temp == pytest.approx(57, abs=0.6)
    assert max(levels[-12:]) - min(levels[-12:]) <= 2


def test_after_a_heavy_scene_the_fans_come_down_within_a_minute_and_a_half() -> None:
    hold = Hold(55)
    scene = Soc(slowest=77.0, fastest=67.5)
    scene.temp = 55.0
    assert scene.run(hold, 55, 9)[-1] == 100
    game = Soc(slowest=58.9, fastest=49.3)
    game.temp = scene.temp

    levels = game.run(hold, 55, 48)

    # Full speed while the SoC cools, then down to about the level it settles at and no way back.
    assert levels[14] <= 50
    assert max(levels[14:]) <= 50
    assert max(levels[-12:]) - min(levels[-12:]) <= 2
    assert game.temp == pytest.approx(55, abs=0.6)


def test_a_temperature_on_its_way_to_the_target_leaves_the_level_found_alone() -> None:
    hold = Hold(60)
    for _ in range(3):
        hold.look(64.0)
    found = hold.level - 16

    # Cooling by two degrees a look, the SoC gets there by itself: only the lean follows it down.
    assert [hold.look(temp) for temp in (62.0, 60.0)] == [found + 13, found + 8]


def test_a_temperature_that_will_not_get_to_the_target_moves_the_level_found() -> None:
    hold = Hold(70)
    for _ in range(3):
        hold.look(53.0)

    # Warming by half a degree a look with 17 to go: the fans are to slow down for good.
    levels = [hold.look(temp) for temp in (53.5, 54.0, 54.5, 55.0, 55.5, 56.0)]

    assert levels[-1] == HOLD_SLOWEST
    hold.aim(56)
    assert hold.look(56.0) == HOLD_SLOWEST


def test_near_the_target_the_firmware_keeps_the_curve_it_has() -> None:
    hold = Hold(60)

    assert [hold.look(temp) for temp in (60.3, 59.7, 60.2, 60.8, 60.0, 59.9)] == [HOLD_START] * 6


def test_a_spike_counts_for_a_third_of_itself() -> None:
    hold = Hold(60)
    for _ in range(3):
        hold.look(60.0)

    # 6 °C over for one look reads as 2 °C: 3% more found, and 8% of lean on top.
    assert hold.look(66.0) == HOLD_START + 3 + 8


def test_another_target_goes_on_from_the_level_found() -> None:
    hold = Hold(60)
    for _ in range(10):
        hold.look(63.0)
    leaning = hold.level

    hold.aim(63)

    # At the new target the 12% of lean go, the level found stays.
    assert hold.look(63.0) == leaning - 12


class Ally:
    """The first ROG Ally as its owner recorded it (2026-11-22), second by second.

    From 60 °C the firmware runs the fans at 5350 rpm at least and lets go at 56 °C; under it the
    fans follow the curve, a step kept for 4 °C on the way down. The SoC goes two thirds of the
    way to where it rests in 25 s.
    """

    FLOOR_RPM = 5350
    # °C over the room per watt, by fan 1's speed: 61.5 °C at 3500 rpm and 15 W, 56 °C at 5350.
    WARMTH = ((3300, 2.47), (3500, 2.43), (5350, 2.07), (6000, 1.95), (7700, 1.78))

    def __init__(self, target: int) -> None:
        self.hold = Hold(target, ROG_ALLY)
        self.temp, self.rpm = 45.0, 3500.0
        self.taken = 0
        """Times the firmware took the fans up to its floor."""
        self._floor = False
        self._curve = hold_curve(self.hold.held, self.hold.level)
        self._step = speed_at(self._curve, self.temp)

    def run(self, watts: float, seconds: int) -> list[float]:
        """Fan 1's speed at each look of the hold, one every 5 s."""
        speeds: list[float] = []
        for second in range(1, seconds + 1):
            self._second(watts)
            if second % 5 == 0:
                level = self.hold.look(self.temp, round(self.rpm))
                curve = hold_curve(self.hold.held, level)
                if curve != self._curve:
                    # A curve written is read anew: the step is the one the temperature asks.
                    self._curve, self._step = curve, speed_at(curve, self.temp)
                speeds.append(self.rpm)
        return speeds

    def _second(self, watts: float) -> None:
        asked = speed_at(self._curve, self.temp)
        self._step = max(asked, min(self._step, speed_at(self._curve, self.temp + 4)))
        if self.temp >= 60 and not self._floor:
            self._floor, self.taken = True, self.taken + 1
        elif self.temp <= 56:
            self._floor = False
        goal = max(ROG_ALLY.rpm_at(self._step), self.FLOOR_RPM if self._floor else 0)
        self.rpm += max(-250.0, min(250.0, goal - self.rpm))
        warmth = next(
            slow + (fast - slow) * (max(self.rpm, low) - low) / (high - low)
            for (low, slow), (high, fast) in pairwise(self.WARMTH)
            if self.rpm <= high
        )
        self.temp += (25 + warmth * watts - self.temp) / 25


def steady(speeds: list[float]) -> bool:
    """Whether the fans kept one speed over the last two minutes."""
    return max(speeds[-24:]) - min(speeds[-24:]) <= 300


def test_the_fans_speed_at_a_level_is_on_the_line_between_the_two_measured() -> None:
    assert ROG_ALLY.rpm_at(15) == 3500
    assert ROG_ALLY.rpm_at(20) == 3800
    assert ROG_ALLY.rpm_at(100) == 7700
    assert XBOX_ALLY_X.rpm_at(4) == 1850


def test_the_rog_ally_holds_a_target_under_its_firmwares_floor_at_one_speed() -> None:
    ally = Ally(58)

    speeds = ally.run(15, 900)

    # On a curve the firmware takes the fans from 3500 to 5350 rpm and back every two minutes.
    assert ally.temp == pytest.approx(58, abs=0.6)
    assert steady(speeds)
    assert speeds[-1] < Ally.FLOOR_RPM - 300
    assert ally.taken == 0


def test_a_target_over_the_floor_is_held_under_it_while_slower_fans_keep_the_soc_there() -> None:
    ally = Ally(65)

    speeds = ally.run(15, 900)

    assert ally.hold.held == 58
    assert ally.temp == pytest.approx(58, abs=0.6)
    assert steady(speeds)
    assert ally.taken == 0


def test_a_soc_that_gets_to_the_floor_all_the_same_is_held_at_the_target_itself() -> None:
    ally = Ally(65)

    speeds = ally.run(20, 900)

    assert ally.hold.held == 65
    assert ally.temp == pytest.approx(65, abs=0.6)
    assert steady(speeds)
    assert ally.hold.level >= 50
    assert ally.taken == 1


def test_a_soc_the_floor_keeps_under_the_target_stays_with_the_fans_at_the_floor() -> None:
    ally = Ally(75)

    speeds = ally.run(20, 900)

    # Slower than the floor the fans cannot go there, and a lower level would change nothing.
    assert ally.hold.level == 50
    assert ally.temp < 70
    assert steady(speeds)


def test_once_the_load_is_lighter_the_fans_go_under_the_floor_again() -> None:
    ally = Ally(65)
    ally.run(20, 600)

    speeds = ally.run(15, 900)

    assert ally.hold.held == 58
    assert ally.temp == pytest.approx(58, abs=0.6)
    assert steady(speeds)
    assert speeds[-1] < Ally.FLOOR_RPM - 300
    assert ally.taken == 1


def test_a_heavy_scene_takes_the_fans_to_the_floor_once_and_not_again_after_it() -> None:
    ally = Ally(58)
    ally.run(15, 600)
    ally.run(30, 45)

    speeds = ally.run(15, 900)

    assert ally.temp == pytest.approx(58, abs=0.6)
    assert steady(speeds)
    assert ally.taken == 1


def test_a_light_load_leaves_the_rog_allys_fans_at_their_slowest() -> None:
    ally = Ally(65)

    speeds = ally.run(10, 600)

    assert ally.hold.level == ROG_ALLY.slowest
    assert speeds[-1] == 3500
    assert ally.taken == 0


def test_while_the_firmware_runs_the_fans_the_level_found_waits() -> None:
    told, run_by_firmware = Hold(58, ROG_ALLY), Hold(58, ROG_ALLY)

    for _ in range(30):
        # A degree under the target: fans that follow the level, and fans kept at the floor.
        told.look(57.0, round(ROG_ALLY.rpm_at(told.level)))
        run_by_firmware.look(57.0, 5350)

    assert told.level == ROG_ALLY.slowest
    # Let go, the fans are to be near the speed that held the SoC, not at their slowest.
    assert run_by_firmware.level >= 30


def test_the_hottest_is_the_warmer_of_the_two_and_unknown_without_them(fake_root: FakeRoot) -> None:
    assert hottest(fake_root.path) is None

    fake_root.hwmon(7, "k10temp", temp1_input=61625)
    assert hottest(fake_root.path) == 61.625

    fake_root.hwmon(5, "amdgpu", temp1_input=64000)
    assert hottest(fake_root.path) == 64.0


def test_fan_1s_speed_is_read_from_the_asus_device_and_unknown_without_it(
    fake_root: FakeRoot,
) -> None:
    assert fan_speed(fake_root.path) is None

    fake_root.hwmon(6, "asus", fan1_input=4600, fan2_input=4700)
    assert fan_speed(fake_root.path) == 4600
