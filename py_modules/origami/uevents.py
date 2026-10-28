# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""The kernel's events about power supplies, so the charger is noticed at once.

Steam writes its own TDP within milliseconds of the charger being plugged in or out (probe 20).
Looking every two seconds, ORIGAMI answered a few seconds later, while the SoC drew 37 W. The
kernel announces each change of a supply on a netlink socket, which needs no D-Bus client.
"""

import asyncio
import socket
from collections.abc import AsyncGenerator, Callable

NETLINK_KOBJECT_UEVENT = 15
KERNEL_EVENTS = 1
"""The multicast group of the events the kernel sends itself, before udev handles them."""
MESSAGE_BYTES = 8192


def open_uevent_socket() -> socket.socket:
    sock = socket.socket(
        socket.AF_NETLINK, socket.SOCK_DGRAM | socket.SOCK_CLOEXEC, NETLINK_KOBJECT_UEVENT
    )
    try:
        sock.bind((0, KERNEL_EVENTS))
    except OSError:
        sock.close()
        raise
    return sock


async def supply_changes(
    *, open_socket: Callable[[], socket.socket] = open_uevent_socket
) -> AsyncGenerator[None]:
    """Yield on every change the kernel reports of a power supply; raise OSError without events."""
    sock = open_socket()
    try:
        sock.settimeout(0.0)  # non-blocking, as asyncio reads it
        loop = asyncio.get_running_loop()
        while True:
            if is_supply_change(await loop.sock_recv(sock, MESSAGE_BYTES)):
                yield
    finally:
        sock.close()


def is_supply_change(message: bytes) -> bool:
    """Whether a uevent ("change@<path>" and KEY=value fields, each ending in NUL) is a supply's."""
    fields = message.split(b"\0")
    return b"ACTION=change" in fields and b"SUBSYSTEM=power_supply" in fields
