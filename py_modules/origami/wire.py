# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

from collections.abc import Sequence
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import cast

from origami.jsonio import JsonValue


def to_wire(value: object) -> JsonValue:
    """Convert a result for the frontend: dataclasses become objects with camelCase keys."""
    if is_dataclass(value) and not isinstance(value, type):
        return {_camel(field.name): to_wire(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return to_wire(value.value)
    if isinstance(value, list | tuple):
        return [to_wire(item) for item in cast("Sequence[object]", value)]
    if value is None or isinstance(value, bool | int | float | str):
        return value
    raise TypeError(f"Cannot send {type(value).__name__} to the frontend")


def from_wire(changes: dict[str, object]) -> dict[str, object]:
    """Keys sent by the frontend (camelCase) as the backend's field names."""
    return {_snake(key): value for key, value in changes.items()}


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.capitalize() for part in rest)


def _snake(name: str) -> str:
    return "".join(f"_{char.lower()}" if char.isupper() else char for char in name)
