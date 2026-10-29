# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from origami.jsonio import parse_object
from origami.proc import CommandError, run
from origami.sysfs import read_text

log = logging.getLogger(__name__)

OS_RELEASE = (Path("etc/os-release"), Path("usr/lib/os-release"))
KERNEL_RELEASE = Path("proc/sys/kernel/osrelease")
COMMAND_TIMEOUT_S = 5

_QUOTED = re.compile(r"""(['"])(.*)\1""", re.DOTALL)
_ESCAPED = re.compile(r"\\(.)", re.DOTALL)


@dataclass(frozen=True, slots=True)
class OsRelease:
    name: str | None
    version_id: str | None
    image_version: str | None
    """Full build of an image-based system, e.g. 44.20261023 on Bazzite."""


@dataclass(frozen=True, slots=True)
class Versions:
    os: OsRelease
    kernel: str | None
    inputplumber: str | None
    decky: str | None


async def read_versions(root: Path, *, decky: str | None) -> Versions:
    os_release, kernel = await asyncio.to_thread(
        lambda: (read_os_release(root), read_text(root / KERNEL_RELEASE))
    )
    return Versions(
        os=os_release,
        kernel=kernel,
        inputplumber=await read_inputplumber_version(),
        decky=decky,
    )


def read_os_release(root: Path) -> OsRelease:
    # os-release(5): /etc/os-release takes precedence over /usr/lib/os-release.
    fields: dict[str, str] = {}
    for path in OS_RELEASE:
        text = read_text(root / path)
        if text is not None:
            fields = parse_os_release(text)
            break
    return OsRelease(
        name=fields.get("NAME"),
        version_id=fields.get("VERSION_ID"),
        image_version=fields.get("OSTREE_VERSION"),
    )


def parse_os_release(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if separator and key.isidentifier():
            fields[key] = _unquote(value)
    return fields


def _unquote(value: str) -> str:
    # Values use shell quoting; shlex is not bundled with Decky's Python.
    match = _QUOTED.fullmatch(value)
    if match is None:
        return _ESCAPED.sub(r"\1", value)
    quote, inner = match.groups()
    return inner if quote == "'" else _ESCAPED.sub(r"\1", inner)


async def read_inputplumber_version() -> str | None:
    try:
        async with asyncio.timeout(COMMAND_TIMEOUT_S):
            output = await run(
                "busctl",
                "--system",
                "--json=short",
                "get-property",
                "org.shadowblip.InputPlumber",
                "/org/shadowblip/InputPlumber/Manager",
                "org.shadowblip.InputManager",
                "Version",
            )
    except (CommandError, TimeoutError) as error:
        log.info("InputPlumber version is not available: %r", error)
        return None
    try:
        value = parse_object(output).get("data")
    except ValueError:
        log.warning("Unexpected busctl output: %r", output)
        return None
    return value if isinstance(value, str) else None
