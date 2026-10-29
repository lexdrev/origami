# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

# Type stub for the module Decky Loader injects at runtime; only what ORIGAMI uses.

DECKY_VERSION: str
DECKY_HOME: str
DECKY_PLUGIN_VERSION: str
DECKY_PLUGIN_DIR: str
DECKY_PLUGIN_SETTINGS_DIR: str
DECKY_PLUGIN_RUNTIME_DIR: str

async def emit(event: str, *args: object) -> None: ...
