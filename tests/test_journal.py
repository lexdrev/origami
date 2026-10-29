# SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
# SPDX-License-Identifier: GPL-3.0-or-later

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from origami.journal import Change, ChangeJournal
from origami.jsonio import JsonValue


def reopened(path: Path) -> ChangeJournal:
    journal = ChangeJournal(path)
    journal.load()
    return journal


def test_empty_without_a_file(tmp_path: Path) -> None:
    assert reopened(tmp_path / "changes.json").entries() == []


def test_first_original_is_kept(tmp_path: Path) -> None:
    path = tmp_path / "changes.json"
    journal = reopened(path)
    assert not journal.recorded("power", "ppt_pl1_spl")

    journal.record("power", "ppt_pl1_spl", 17)
    journal.record("power", "ppt_pl1_spl", 20)

    assert reopened(path).recorded("power", "ppt_pl1_spl")
    assert reopened(path).entries() == [Change("power", "ppt_pl1_spl", 17)]


def test_structured_originals_survive_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "changes.json"
    curve: JsonValue = {"temps": [30, 40], "pwm": [0, 25], "enable": None}

    reopened(path).record("fans", "curve", curve)

    assert reopened(path).entries() == [Change("fans", "curve", curve)]


def test_forgetting_the_last_change_removes_the_file(tmp_path: Path) -> None:
    path = tmp_path / "changes.json"
    journal = reopened(path)
    journal.record("power", "boost", 1)

    journal.forget("power", "boost")
    journal.forget("power", "boost")

    assert not path.exists()
    assert reopened(path).entries() == []


@pytest.mark.parametrize(
    "content",
    ["{", '{"changes": {}}', '{"changes": [1]}', '{"changes": [{"module": "power"}]}'],
)
def test_unreadable_journal_starts_empty(
    tmp_path: Path, content: str, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "changes.json"
    path.write_text(content, encoding="utf-8")

    assert reopened(path).entries() == []
    assert "unreadable" in caplog.text


def test_the_original_is_looked_up_by_module_and_key(tmp_path: Path) -> None:
    journal = reopened(tmp_path / "changes.json")
    journal.record("power", "cpu_boost", True)

    assert reopened(tmp_path / "changes.json").original("power", "cpu_boost") is True
    assert journal.original("power", "tdp") is None


def test_changes_from_many_threads_all_reach_the_file(tmp_path: Path) -> None:
    path = tmp_path / "changes.json"
    journal = reopened(path)

    with ThreadPoolExecutor(max_workers=8) as pool:
        for index in range(40):
            pool.submit(journal.record, "module", f"key{index}", index)

    assert len(journal.entries()) == 40
    assert len(reopened(path).entries()) == 40
