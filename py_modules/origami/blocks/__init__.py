# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""ORIGAMI's blocks, one for each tile of the main screen and one for the buttons.

A block drives its own hardware through the modules beside this package: it sends a change before
the settings keep it, follows the settings it is given, gives its hardware back as it was before
ORIGAMI, with the journal's help, and stops without waiting. origami.app holds the settings and
the journal and calls the blocks in turn.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from origami.decky_plugins import Conflicts
from origami.journal import ChangeJournal


@dataclass(frozen=True, slots=True)
class Context:
    """What every block shares: the filesystem root, the journal and the other plugins."""

    root: Path
    journal: ChangeJournal
    conflicts: Callable[[], Awaitable[Conflicts]]
    """Which enabled plugins drive hardware ORIGAMI also drives, read anew on every call."""
