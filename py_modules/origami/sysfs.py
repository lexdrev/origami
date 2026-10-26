# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""Reading kernel attributes.

Every path is built from a filesystem root passed by the caller, so tests can
run against a fake tree instead of the real /sys.
"""

import logging
from pathlib import Path

log = logging.getLogger(__name__)

HWMON = Path("sys/class/hwmon")


def read_text(path: Path) -> str | None:
    """Return the stripped attribute value, or None if it cannot be read.

    Missing attributes are normal on other hardware; read errors (EIO from the
    embedded controller, for example) are logged and treated the same way.
    """
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except OSError as error:
        log.debug("Cannot read %s: %s", path, error)
        return None


def read_int(path: Path) -> int | None:
    text = read_text(path)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        log.debug("Unexpected value in %s: %r", path, text)
        return None


def find_hwmon(root: Path, name: str) -> Path | None:
    """Find a hwmon device by driver name; hwmonN numbering changes between boots."""
    try:
        devices = sorted((root / HWMON).iterdir())
    except OSError:
        return None
    return next((device for device in devices if read_text(device / "name") == name), None)
