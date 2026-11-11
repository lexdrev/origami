# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""What every game's own settings begin with: the game and whether they apply."""

from typing import cast

from origami.jsonio import expect_bool

MAX_GAME_NAME = 200
"""Characters of a game's name kept for the list of profiles."""


def parse_game(value: object, what: str) -> tuple[dict[str, object], int, str, bool]:
    """A game's profile sent by the frontend or saved: its fields, app id, name and "active".

    `what` names the settings in the errors ("power", "sound"). Raises ValueError on bad input.
    """
    if not isinstance(value, dict):
        raise ValueError(f"a game's {what} must be an object")
    data = cast("dict[str, object]", value)
    app_id = data.get("app_id")
    if not isinstance(app_id, int) or isinstance(app_id, bool) or app_id <= 0:
        raise ValueError("app_id must be a positive Steam app id")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"a game's {what} needs the game's name")
    active = expect_bool("active", data.get("active", True))
    return data, app_id, name.strip()[:MAX_GAME_NAME], active
