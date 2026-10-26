# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

"""Decky's Python is a PyInstaller bundle without the full standard library.

An import that works on a developer machine can fail on the console, so every
module the backend imports must be in the list taken from the Decky binary.
"""

import ast
from pathlib import Path

PROJECT = Path(__file__).parent.parent
OWN_MODULES = {"origami", "decky"}
# collections/__init__.py registers collections.abc in sys.modules itself.
PROVIDED_BY_PARENT = {"collections.abc"}


def bundled_modules() -> set[str]:
    lines = (PROJECT / "tests" / "decky_modules.txt").read_text(encoding="utf-8").splitlines()
    return {line for line in lines if line and not line.startswith("#")}


def imported_modules(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def test_backend_imports_are_bundled_with_decky() -> None:
    sources = [PROJECT / "main.py", *(PROJECT / "py_modules").rglob("*.py")]
    available = bundled_modules() | PROVIDED_BY_PARENT
    missing = {
        f"{module} ({source.relative_to(PROJECT)})"
        for source in sources
        for module in imported_modules(source)
        if module.split(".")[0] not in OWN_MODULES and module not in available
    }

    assert not missing, f"Not available in Decky's Python: {sorted(missing)}"
