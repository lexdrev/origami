# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""The CPU's frequency boost and the ceiling it leaves (BUGS.md, B02 and B03).

With the boost off, amd-pstate caps the cores at their nominal 2.0 GHz. After the charger is
plugged in or out, or a game starts, the fast cores may run far above the cap, up to 5 GHz, while
the boost flags and every scaling_max_freq still read capped (probes 20 and 21): the cap did not
reach the CPU. Switching the boost on and off again does not help, and neither does lowering the
cap and raising it back at once. ORIGAMI lowers it on every core, waits a moment, and raises it
back.
"""

import asyncio
from pathlib import Path

from origami.sysfs import read_int

BOOST = Path("sys/devices/system/cpu/cpufreq/boost")
CPUFREQ = Path("sys/devices/system/cpu/cpufreq")
KICK_KHZ = 30_000
"""How far the cap is lowered for a moment to program it again."""
KICK_HOLD_SECONDS = 0.2
"""How long the lowered cap stays."""


def read_boost(root: Path) -> bool | None:
    raw = read_int(root / BOOST)
    return None if raw is None else raw != 0


def write_boost(root: Path, *, on: bool) -> None:
    (root / BOOST).write_text("1\n" if on else "0\n", encoding="utf-8")


def frequency_cap(root: Path) -> int | None:
    """The lowest cap of the cores in kHz, as the kernel applies it; None without cpufreq."""
    caps = [cap for policy in _policies(root) if (cap := _applied_cap(policy))]
    return min(caps, default=None)


def fastest_core(root: Path) -> int | None:
    """The frequency of the fastest core now, in kHz."""
    speeds = [
        speed for policy in _policies(root) if (speed := read_int(policy / "scaling_cur_freq"))
    ]
    return max(speeds, default=None)


async def program_cap(root: Path) -> None:
    """Have every core's cap reach the CPU again: lower it on all cores a moment, then raise it.

    The caps are written at once, without awaiting, so a cancelled call never leaves them lowered.
    """
    lowered = lower_caps(root)
    try:
        await asyncio.sleep(KICK_HOLD_SECONDS)
    finally:
        raise_caps(lowered)


def lower_caps(root: Path) -> list[tuple[Path, int]]:
    """Lower every core's cap a step; return where each goes back to, for raise_caps.

    A cap written to scaling_max_freq stays as a limit of its own, also once the boost is on. So a
    cap lower than the hardware's top is someone's choice and goes back as it was; any other goes
    back to the top with the boost, and the boost flag alone caps the cores, as before ORIGAMI.
    """
    lowered: list[tuple[Path, int]] = []
    try:
        for policy in _policies(root):
            cap, top = read_int(policy / "scaling_max_freq"), read_int(policy / "cpuinfo_max_freq")
            if cap is None or top is None:
                continue
            target = policy / "scaling_max_freq"
            restore = cap if cap < top else read_int(policy / "amd_pstate_max_freq") or top
            target.write_text(f"{cap - KICK_KHZ}\n", encoding="utf-8")
            lowered.append((target, restore))
    except OSError:
        raise_caps(lowered)
        raise
    return lowered


def raise_caps(lowered: list[tuple[Path, int]]) -> None:
    for target, restore in lowered:
        target.write_text(f"{restore}\n", encoding="utf-8")


def _applied_cap(policy: Path) -> int | None:
    cap, top = read_int(policy / "scaling_max_freq"), read_int(policy / "cpuinfo_max_freq")
    if cap is None:
        return None
    return cap if top is None else min(cap, top)


def _policies(root: Path) -> list[Path]:
    return sorted((root / CPUFREQ).glob("policy*"))
