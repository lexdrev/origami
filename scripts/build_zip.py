# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Package the plugin as the zip that Decky installs: ORIGAMI-<version>.zip, one Origami/ folder
inside.

The archive is reproducible: entries are sorted, timestamps come from
SOURCE_DATE_EPOCH (or the zip epoch, 1980-01-01) and permissions are fixed.
Run `npm run build` and scripts/build_bpf.sh first.
"""

import hashlib
import json
import os
import sys
import time
import zipfile
from pathlib import Path

NAME = "ORIGAMI"
FOLDER = "Origami"
FILES = (
    "plugin.json",
    "package.json",
    "main.py",
    "LICENSE",
    "README.md",
    "THIRD_PARTY_NOTICES.md",
    "dist/index.js",
    "bin/rumble.bpf.o",
)
PACKAGES = ("py_modules",)
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def plugin_files(project: Path) -> list[Path]:
    files = [project / name for name in FILES]
    for package in PACKAGES:
        files.extend(path for path in (project / package).rglob("*.py") if path.is_file())
    missing = [str(path.relative_to(project)) for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing files: {', '.join(missing)}")
    return sorted(files, key=lambda path: path.relative_to(project).as_posix())


def timestamp() -> tuple[int, int, int, int, int, int]:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch is None:
        return ZIP_EPOCH
    moment = time.gmtime(int(epoch))
    return max(ZIP_EPOCH, moment[:6])


def build(project: Path, output_dir: Path) -> Path:
    version = json.loads((project / "package.json").read_text(encoding="utf-8"))["version"]
    archive = output_dir / f"{NAME}-{version}.zip"
    output_dir.mkdir(parents=True, exist_ok=True)
    date_time = timestamp()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in plugin_files(project):
            entry = zipfile.ZipInfo(f"{FOLDER}/{path.relative_to(project).as_posix()}", date_time)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            entry.create_system = 3  # Unix, so the permissions above are honoured
            zf.writestr(entry, path.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_name(f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n", "utf-8")
    return archive


def main() -> None:
    project = Path(__file__).resolve().parent.parent
    archive = build(project, project / "out")
    sys.stdout.write(f"{archive}\n")


if __name__ == "__main__":
    main()
