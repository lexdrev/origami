# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
from pathlib import Path

import pytest

from origami.cpu import fastest_core, frequency_cap, program_cap, read_boost, write_boost

from fakes import FakeRoot

CPUFREQ = "sys/devices/system/cpu/cpufreq"


def test_the_boost_flag(powered: FakeRoot) -> None:
    assert read_boost(powered.path) is False

    write_boost(powered.path, on=True)

    assert read_boost(powered.path) is True
    assert (powered.path / CPUFREQ / "boost").read_text(encoding="utf-8") == "1\n"


def test_the_cap_and_the_fastest_core(powered: FakeRoot) -> None:
    powered.write(f"{CPUFREQ}/policy2/scaling_cur_freq", 3_500_000)

    assert frequency_cap(powered.path) == 2_000_000
    assert fastest_core(powered.path) == 3_500_000


def test_without_cpufreq_there_is_nothing_to_read(fake_root: FakeRoot) -> None:
    assert frequency_cap(fake_root.path) is None
    assert fastest_core(fake_root.path) is None


def test_the_cap_is_lowered_on_every_core_and_raised_back_to_the_boosted_top(
    powered: FakeRoot, monkeypatch: pytest.MonkeyPatch
) -> None:
    writes: list[tuple[str, str]] = []
    write_text = Path.write_text

    def recorded(path: Path, text: str, encoding: str | None = None) -> int:
        writes.append((path.parent.name, text))
        return write_text(path, text, encoding=encoding)

    monkeypatch.setattr(Path, "write_text", recorded)

    asyncio.run(program_cap(powered.path))

    # All four cores go down first, then all come back, past the 2.0 GHz the boost flag keeps.
    assert writes == [(f"policy{cpu}", "1970000\n") for cpu in range(4)] + [
        (f"policy{cpu}", "5090910\n") for cpu in range(4)
    ]
    assert frequency_cap(powered.path) == 2_000_000


def test_a_cap_someone_chose_comes_back_as_it_was(powered: FakeRoot) -> None:
    for cpu in range(4):
        powered.write(f"{CPUFREQ}/policy{cpu}/scaling_max_freq", 1_600_000)

    asyncio.run(program_cap(powered.path))

    assert (powered.path / CPUFREQ / "policy3" / "scaling_max_freq").read_text(
        encoding="utf-8"
    ) == "1600000\n"
