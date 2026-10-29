# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, text: str) -> None:
    """Replace a file so readers see either the old or the new content.

    The plugin runs as root in folders the user owns: the temporary file is
    created with O_EXCL | O_NOFOLLOW (tempfile does this), and rename() replaces
    a symlink at the target instead of writing through it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    _fsync_directory(path.parent)


def _fsync_directory(directory: Path) -> None:
    # Makes the rename durable on power loss. O_DIRECTORY is POSIX-only;
    # the plugin runs on Linux, the check keeps the tests runnable on Windows.
    flag = getattr(os, "O_DIRECTORY", None)
    if flag is None:
        return
    fd = os.open(directory, os.O_RDONLY | flag)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
