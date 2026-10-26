# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass

import pytest

from origami.settings import Language
from origami.wire import to_wire


@dataclass(frozen=True)
class Inner:
    cpu_temp_c: float | None


@dataclass(frozen=True)
class Outer:
    tdp_limit_w: int
    language: Language
    vibration_pct: tuple[int, int]
    inner: list[Inner]


def test_dataclasses_become_camel_case_objects() -> None:
    value = Outer(17, Language.RU, (50, 50), [Inner(61.5), Inner(None)])

    assert to_wire(value) == {
        "tdpLimitW": 17,
        "language": "ru",
        "vibrationPct": [50, 50],
        "inner": [{"cpuTempC": 61.5}, {"cpuTempC": None}],
    }


def test_unknown_types_are_rejected() -> None:
    with pytest.raises(TypeError, match="set"):
        to_wire({1, 2})
