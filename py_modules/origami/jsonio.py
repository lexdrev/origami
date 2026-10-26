# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from typing import cast

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None


def parse_object(text: str) -> dict[str, JsonValue]:
    """Parse a JSON document that must be an object; raise ValueError otherwise."""
    data = cast("JsonValue", json.loads(text))
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


def expect_bool(key: str, value: object) -> bool:
    """Return a JSON boolean; raise ValueError for anything else, numbers included."""
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be true or false")
    return value
