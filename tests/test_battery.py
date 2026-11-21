# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import itertools
import json
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from origami.battery import (
    REMEMBERED_MINUTES,
    BatteryWatch,
    Charge,
    Drain,
    Forecast,
    GameDrains,
    read_charge,
)
from origami.blocks import Context
from origami.blocks import battery as battery_block
from origami.blocks.battery import BatteryBlock
from origami.decky_plugins import Conflicts
from origami.journal import ChangeJournal

from fakes import FakeRoot

FULL = 74_000_000
GAME = 1920490
LOOK = 10


def charge(energy_wh: float, *, power_w: float | None = 20, discharging: bool = True) -> Charge:
    return Charge(
        discharging=discharging,
        energy_uwh=round(energy_wh * 1_000_000),
        full_uwh=FULL,
        power_uw=None if power_w is None else round(power_w * 1_000_000),
    )


class Draining:
    """A battery at 40 Wh that a watch looks at every ten seconds while it loses energy.

    The gauge tells 20 W all the while, whatever the battery loses.
    """

    def __init__(self, watch: BatteryWatch) -> None:
        self.watch = watch
        self.energy_wh = 40.0
        self.at = 0

    def run(self, seconds: int, watts: float, *, game: int | None = None) -> Forecast | None:
        """Lose `watts` for the seconds, from where the last run ended; the last look's forecast."""
        forecast = None
        for passed in range(0, seconds + 1, LOOK):
            left = self.energy_wh - watts * passed / 3600
            forecast = self.watch.look(self.at + passed, 0, charge(left), game=game, tdp=17)
        self.at += seconds
        self.energy_wh -= watts * seconds / 3600
        return forecast


@pytest.fixture
def drains(tmp_path: Path) -> GameDrains:
    return GameDrains(tmp_path / "data" / "battery.json")


def test_the_first_look_counts_with_the_power_the_gauge_tells(drains: GameDrains) -> None:
    forecast = BatteryWatch(drains).look(0, 0, charge(40, power_w=20), game=None, tdp=17)

    # 40 Wh less the tenth of 74 Wh kept in reserve, at 20 W.
    assert forecast == Forecast(minutes_left=98, until_pct=10, drain_w=20.0)


def test_a_full_window_counts_with_the_energy_lost_alone(drains: GameDrains) -> None:
    # The gauge tells 20 W, as in a calm moment, while the battery loses 30 W.
    forecast = Draining(BatteryWatch(drains)).run(300, 30)

    assert forecast is not None
    assert forecast.drain_w == 30.0
    assert forecast.minutes_left == round((40 - 2.5 - 7.4) / 30 * 60)


def test_the_measured_draw_comes_in_as_the_window_fills(drains: GameDrains) -> None:
    battery = Draining(BatteryWatch(drains))

    under_a_minute = battery.run(50, 30)
    # Topped up meanwhile, so the measuring starts anew.
    battery.energy_wh = 40
    half_way = battery.run(150, 30)

    assert under_a_minute is not None
    assert half_way is not None
    assert under_a_minute.drain_w == 20.0
    # Half the window is measured, the other half is the gauge's.
    assert half_way.drain_w == 25.0


def test_the_window_forgets_what_is_older_than_five_minutes(drains: GameDrains) -> None:
    battery = Draining(BatteryWatch(drains))
    battery.run(300, 30)

    forecast = battery.run(300, 12)

    assert forecast is not None
    assert forecast.drain_w == 12.0


def test_under_the_reserve_the_time_is_told_to_an_empty_battery(drains: GameDrains) -> None:
    forecast = BatteryWatch(drains).look(0, 0, charge(5, power_w=20), game=None, tdp=17)

    assert forecast == Forecast(minutes_left=15, until_pct=0, drain_w=20.0)


def test_a_battery_without_its_full_charge_is_told_to_empty(drains: GameDrains) -> None:
    unknown_full = Charge(
        discharging=True, energy_uwh=40_000_000, full_uwh=None, power_uw=20_000_000
    )

    forecast = BatteryWatch(drains).look(0, 0, unknown_full, game=None, tdp=17)

    assert forecast == Forecast(minutes_left=120, until_pct=0, drain_w=20.0)


@pytest.mark.parametrize(
    "look",
    [None, charge(40, discharging=False), Charge(True, None, FULL, 20_000_000)],
    ids=["no battery", "on the charger", "no energy told"],
)
def test_nothing_is_told_without_a_draining_battery(
    drains: GameDrains, look: Charge | None
) -> None:
    assert BatteryWatch(drains).look(0, 0, look, game=None, tdp=17) is None


@pytest.mark.parametrize("gauge_w", [None, 0, -20, 1.5, 400])
def test_nothing_is_told_while_nothing_plausible_tells_the_draw(
    drains: GameDrains, gauge_w: float | None
) -> None:
    look = charge(40, power_w=gauge_w)

    assert BatteryWatch(drains).look(0, 0, look, game=None, tdp=17) is None


def test_a_gauge_that_stands_still_measures_nothing(drains: GameDrains) -> None:
    forecast = Draining(BatteryWatch(drains)).run(300, 0, game=GAME)

    assert forecast is not None
    assert forecast.drain_w == 20.0
    assert drains.known(GAME, 17) is None


def test_the_measuring_starts_when_the_gauge_moves(drains: GameDrains) -> None:
    # Off the charger at a full charge the gauge stands still for minutes, then tells 30 W.
    battery = Draining(BatteryWatch(drains))
    battery.run(300, 0)

    # It makes up for a part of the time it stood in one step, as on the console.
    battery.energy_wh -= 0.739
    forecast = battery.run(120, 30)

    # Two minutes of five are measured: neither the minutes it stood nor that step count.
    assert forecast is not None
    assert forecast.drain_w == 24.0


def test_a_gauge_that_stops_in_the_middle_stops_the_measuring(drains: GameDrains) -> None:
    battery = Draining(BatteryWatch(drains))
    battery.run(300, 30)

    stood = battery.run(40, 0)
    battery.energy_wh -= 0.3
    moved = battery.run(60, 30)

    assert stood is not None
    assert moved is not None
    assert stood.drain_w == 20.0
    # A minute after it moved, a fifth of the window is measured again.
    assert moved.drain_w == 22.0


def test_a_games_minute_starts_when_the_gauge_moves(drains: GameDrains) -> None:
    battery = Draining(BatteryWatch(drains))
    battery.run(300, 0, game=GAME)

    battery.energy_wh -= 0.739
    battery.run(120, 30, game=GAME)

    known = drains.known(GAME, 17)
    assert known is not None
    assert (known.minutes, known.watts) == (2, pytest.approx(30.0))


def test_a_charge_the_gauge_corrected_is_not_a_draw(drains: GameDrains) -> None:
    battery = Draining(BatteryWatch(drains))
    battery.run(300, 30)

    battery.energy_wh -= 10
    forecast = battery.run(10, 30)

    assert forecast is not None
    assert forecast.drain_w == 20.0


def test_one_failed_read_of_the_energy_keeps_the_minutes_measured(drains: GameDrains) -> None:
    battery = Draining(BatteryWatch(drains))
    battery.run(300, 30)
    unread = Charge(discharging=True, energy_uwh=None, full_uwh=FULL, power_uw=20_000_000)

    failed = battery.watch.look(battery.at + 5, 0, unread, game=None, tdp=17)
    forecast = battery.run(10, 30)

    assert failed is None
    assert forecast is not None
    assert forecast.drain_w == 30.0


def test_a_failed_read_does_not_carry_the_minutes_over_to_another_load(
    drains: GameDrains,
) -> None:
    battery = Draining(BatteryWatch(drains))
    battery.run(300, 30)
    unread = Charge(discharging=True, energy_uwh=None, full_uwh=FULL, power_uw=20_000_000)

    battery.watch.look(battery.at + 5, 0, unread, game=GAME, tdp=17)
    forecast = battery.watch.look(battery.at + 10, 0, charge(37), game=GAME, tdp=17)

    assert forecast is not None
    assert forecast.drain_w == 20.0


def test_the_charger_starts_the_measuring_anew(drains: GameDrains) -> None:
    watch = BatteryWatch(drains)
    Draining(watch).run(300, 30)

    on_charger = watch.look(310, 0, charge(38, discharging=False), game=None, tdp=17)
    back = watch.look(320, 0, charge(38.5, power_w=12), game=None, tdp=17)

    assert on_charger is None
    assert back is not None
    assert back.drain_w == 12.0


def test_sleep_starts_the_measuring_anew(drains: GameDrains) -> None:
    watch = BatteryWatch(drains)
    Draining(watch).run(300, 30)

    # Two hours asleep lost 1 Wh while the monotonic clock stood still.
    forecast = watch.look(310, 7200, charge(36.5, power_w=14), game=None, tdp=17)

    assert forecast is not None
    assert forecast.drain_w == 14.0


@pytest.mark.parametrize(("game", "tdp"), [(GAME, 17), (None, 25)], ids=["a game", "the TDP"])
def test_another_load_starts_the_measuring_anew(
    drains: GameDrains, game: int | None, tdp: int
) -> None:
    watch = BatteryWatch(drains)
    Draining(watch).run(300, 12)

    forecast = watch.look(310, 0, charge(39, power_w=31), game=game, tdp=tdp)

    assert forecast is not None
    assert forecast.drain_w == 31.0


def test_a_games_minutes_go_into_its_average(drains: GameDrains) -> None:
    battery = Draining(BatteryWatch(drains))

    battery.run(120, 30, game=GAME)
    battery.run(60, 24, game=GAME)

    known = drains.known(GAME, 17)
    assert known is not None
    assert known.minutes == 3
    assert known.watts == pytest.approx(28.0)
    assert drains.known(GAME, 25) is None


def test_the_menu_is_no_games_draw(drains: GameDrains, tmp_path: Path) -> None:
    Draining(BatteryWatch(drains)).run(300, 12)

    drains.save()

    assert not (tmp_path / "data" / "battery.json").exists()


def test_a_game_starts_with_the_draw_of_its_runs_before(drains: GameDrains) -> None:
    drains.add_minute(GAME, 17, 30)
    watch = BatteryWatch(drains)

    # The game loads: the gauge tells 12 W, the runs before 30 W.
    first = watch.look(0, 0, charge(40, power_w=12), game=GAME, tdp=17)
    at_another_tdp = watch.look(10, 0, charge(40, power_w=12), game=GAME, tdp=25)

    assert first is not None
    assert at_another_tdp is not None
    assert first.drain_w == 30.0
    assert at_another_tdp.drain_w == 12.0


def test_older_play_fades_from_the_average(drains: GameDrains) -> None:
    for _ in range(REMEMBERED_MINUTES * 4):
        drains.add_minute(GAME, 17, 30)
    for _ in range(REMEMBERED_MINUTES * 4):
        drains.add_minute(GAME, 17, 20)

    known = drains.known(GAME, 17)
    assert known is not None
    assert known.minutes == REMEMBERED_MINUTES
    assert known.watts == pytest.approx(20.0, abs=0.5)


def test_the_averages_are_kept_between_runs(drains: GameDrains, tmp_path: Path) -> None:
    drains.add_minute(GAME, 17, 29.456)
    drains.add_minute(GAME, None, 31)
    drains.save()

    again = GameDrains(tmp_path / "data" / "battery.json")
    again.load()

    assert again.known(GAME, 17) == Drain(29.46, 1)
    assert again.known(GAME, None) == Drain(31.0, 1)


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[]",
        '{"version": 2, "drains": []}',
        '{"version": 1, "drains": {}}',
        '{"version": 1, "drains": [{"app_id": "x", "tdp": 17, "watts": 30, "minutes": 1}]}',
        '{"version": 1, "drains": [{"app_id": 1, "tdp": 17, "watts": 0, "minutes": 1}]}',
        '{"version": 1, "drains": [{"app_id": 1, "tdp": 17, "watts": true, "minutes": 1}]}',
        '{"version": 1, "drains": [{"app_id": 1, "tdp": 17, "watts": NaN, "minutes": 1}]}',
        '{"version": 1, "drains": [{"app_id": 1, "tdp": 17, "watts": Infinity, "minutes": 1}]}',
        '{"version": 1, "drains": [{"app_id": 1, "tdp": 17, "watts": 0.5, "minutes": 1}]}',
        "\udcff",
    ],
)
def test_an_unreadable_history_starts_empty_and_is_replaced(tmp_path: Path, text: str) -> None:
    path = tmp_path / "battery.json"
    # The last one is a byte that is no UTF-8.
    path.write_text(text, encoding="utf-8", errors="surrogateescape")
    drains = GameDrains(path)

    drains.load()
    drains.add_minute(GAME, 17, 30)
    drains.save()

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "version": 1,
        "drains": [{"app_id": GAME, "tdp": 17, "watts": 30, "minutes": 1}],
    }


def test_the_charge_is_read_from_the_consoles_battery(powered: FakeRoot) -> None:
    powered.write("sys/class/power_supply/ASUS_PAD/type", "Battery")
    powered.write("sys/class/power_supply/ASUS_PAD/scope", "Device")
    powered.write("sys/class/power_supply/ASUS_PAD/status", "Charging")

    assert read_charge(powered.path) == Charge(
        discharging=True, energy_uwh=40_000_000, full_uwh=74_348_000, power_uw=20_000_000
    )


@pytest.mark.parametrize("status", ["Charging", "Not charging", "Full", "Unknown"])
def test_only_a_discharging_battery_drains(powered: FakeRoot, status: str) -> None:
    powered.write("sys/class/power_supply/BAT0/status", status)

    look = read_charge(powered.path)

    assert look is not None
    assert look.discharging is False


def test_no_battery_no_charge(ally_x: FakeRoot) -> None:
    assert read_charge(ally_x.path) is None


def make_block(
    root: FakeRoot, tmp_path: Path, clock: Callable[[], float] = time.monotonic
) -> BatteryBlock:
    async def no_conflicts() -> Conflicts:
        return Conflicts(
            lighting=None,
            saturation=None,
            vibration=None,
            triggers=None,
            power=None,
            boost=None,
            fans=None,
            sound=None,
            sharpness=None,
        )

    journal = ChangeJournal(tmp_path / "data" / "changes.json")
    context = Context(root.path, journal, no_conflicts)
    return BatteryBlock(context, tmp_path / "data" / "battery.json", clock=clock)


async def eventually(done: Callable[[], bool]) -> None:
    """Wait for what the block does in its own time, five seconds at most."""
    for _ in range(500):
        if done():
            return
        await asyncio.sleep(0.01)
    pytest.fail("the block did not get there in five seconds")


def test_the_block_looks_as_it_starts_and_keeps_looking(
    powered: FakeRoot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(battery_block, "LOOK_SECONDS", 0.01)

    async def scenario() -> None:
        block = make_block(powered, tmp_path)
        assert block.forecast() is None
        await block.start()
        # 40 Wh less a tenth of 74.3 Wh, at the gauge's 20 W and then 30 W.
        await eventually(lambda: block.forecast() == Forecast(98, 10, 20.0))
        powered.write("sys/class/power_supply/BAT0/power_now", 30_000_000)
        await eventually(lambda: block.forecast() == Forecast(65, 10, 30.0))
        block.stop()
        # Stopped, the block tells nothing instead of its last look for good.
        await eventually(lambda: block.forecast() is None)

    asyncio.run(scenario())


def test_the_block_saves_a_games_average_while_it_is_played(
    powered: FakeRoot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(battery_block, "LOOK_SECONDS", 0.01)
    history = tmp_path / "data" / "battery.json"
    # Every look comes ten seconds after the one before and finds the battery 30 W lower.
    seconds = itertools.count(0, LOOK)
    looks = itertools.count()

    def draining(_root: Path) -> Charge:
        return charge(40 - next(looks) * 30 * LOOK / 3600)

    monkeypatch.setattr(battery_block, "read_charge", draining)

    async def scenario() -> None:
        block = make_block(powered, tmp_path, clock=lambda: float(next(seconds)))
        block.set_game(GAME)
        await block.start()
        await eventually(history.exists)
        block.stop()

    asyncio.run(scenario())

    # Saved five minutes after the first look, with the five minutes measured by then.
    (saved,) = json.loads(history.read_text(encoding="utf-8"))["drains"]
    assert (saved["app_id"], saved["tdp"], saved["minutes"]) == (GAME, 17, 5)
    assert saved["watts"] == pytest.approx(30, abs=0.01)
