# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import socket
from contextlib import aclosing

from origami.uevents import is_supply_change, supply_changes

# As the kernel sends them: "<action>@<path>", then KEY=value fields, each ending in NUL.
CHARGER = (
    b"change@/devices/platform/ACPI0003:00/power_supply/AC0\0ACTION=change\0"
    b"DEVPATH=/devices/platform/ACPI0003:00/power_supply/AC0\0SUBSYSTEM=power_supply\0"
    b"POWER_SUPPLY_NAME=AC0\0POWER_SUPPLY_TYPE=Mains\0POWER_SUPPLY_ONLINE=1\0SEQNUM=5123\0"
)
SCREEN = b"change@/devices/pci0000:00/drm/card1\0ACTION=change\0SUBSYSTEM=drm\0HOTPLUG=1\0"


def test_supply_changes_are_told_from_other_events() -> None:
    assert is_supply_change(CHARGER)
    assert not is_supply_change(SCREEN)
    assert not is_supply_change(CHARGER.replace(b"ACTION=change", b"ACTION=add"))


def test_each_supply_change_is_yielded_and_the_socket_closed_after() -> None:
    kernel, plugin = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)

    async def scenario() -> int:
        kernel.send(SCREEN)
        kernel.send(CHARGER)
        kernel.send(CHARGER)
        seen = 0
        async with aclosing(supply_changes(open_socket=lambda: plugin)) as changes:
            async for _ in changes:
                seen += 1
                if seen == 2:
                    break
        return seen

    try:
        assert asyncio.run(scenario()) == 2
        assert plugin.fileno() == -1
    finally:
        kernel.close()
