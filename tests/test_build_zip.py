# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib.util
import json
import zipfile
from pathlib import Path
from types import ModuleType

import pytest


def load_script() -> ModuleType:
    path = Path(__file__).parent.parent / "scripts" / "build_zip.py"
    spec = importlib.util.spec_from_file_location("build_zip", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_zip = load_script()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    files = {
        "plugin.json": '{"name": "ORIGAMI"}',
        "package.json": json.dumps({"name": "origami", "version": "1.2.3"}),
        "main.py": "",
        "LICENSE": "GPL",
        "README.md": "",
        "dist/index.js": "",
        "bin/rumble.bpf.o": "",
        "bpf/rumble.bpf.c": "",
        "py_modules/origami/__init__.py": "",
        "py_modules/origami/app.py": "",
        "py_modules/origami/__pycache__/app.cpython-314.pyc": "",
        "src/index.tsx": "",
    }
    for name, content in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(content, encoding="utf-8")
    return root


def test_archive_has_one_folder_with_plugin_files_only(project: Path, tmp_path: Path) -> None:
    archive = build_zip.build(project, tmp_path / "out")

    assert archive.name == "Origami-1.2.3.zip"
    with zipfile.ZipFile(archive) as zf:
        assert zf.namelist() == [
            "Origami/LICENSE",
            "Origami/README.md",
            "Origami/bin/rumble.bpf.o",
            "Origami/dist/index.js",
            "Origami/main.py",
            "Origami/package.json",
            "Origami/plugin.json",
            "Origami/py_modules/origami/__init__.py",
            "Origami/py_modules/origami/app.py",
        ]


def test_archive_is_reproducible(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1793000000")
    first = build_zip.build(project, tmp_path / "a").read_bytes()
    (project / "main.py").touch()
    second = build_zip.build(project, tmp_path / "b").read_bytes()

    assert first == second


def test_checksum_file(project: Path, tmp_path: Path) -> None:
    archive = build_zip.build(project, tmp_path / "out")
    checksum = archive.with_name("Origami-1.2.3.zip.sha256").read_text(encoding="utf-8")

    assert checksum.endswith("  Origami-1.2.3.zip\n")
    assert len(checksum.split()[0]) == 64


def test_missing_bundle_is_reported(project: Path, tmp_path: Path) -> None:
    (project / "dist/index.js").unlink()

    with pytest.raises(FileNotFoundError, match=r"dist/index\.js"):
        build_zip.build(project, tmp_path / "out")
