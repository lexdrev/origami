# SPDX-FileCopyrightText: 2026 lexdrev
# SPDX-License-Identifier: GPL-3.0-or-later

from origami.sysfs import find_hwmon, read_int, read_text

from fakes import FakeRoot


def test_read_text_strips_the_trailing_newline(fake_root: FakeRoot) -> None:
    assert read_text(fake_root.write("sys/a", "balanced")) == "balanced"


def test_missing_attribute_reads_as_none(fake_root: FakeRoot) -> None:
    assert read_text(fake_root.path / "sys/missing") is None
    assert read_int(fake_root.path / "sys/missing") is None


def test_non_numeric_value_reads_as_none(fake_root: FakeRoot) -> None:
    assert read_int(fake_root.write("sys/a", "auto")) is None


def test_hwmon_is_found_by_name_not_by_number(fake_root: FakeRoot) -> None:
    fake_root.hwmon(0, "nvme")
    expected = fake_root.hwmon(4, "asus")

    assert find_hwmon(fake_root.path, "asus") == expected
    assert find_hwmon(fake_root.path, "k10temp") is None


def test_hwmon_lookup_without_hwmon_class(fake_root: FakeRoot) -> None:
    assert find_hwmon(fake_root.path, "asus") is None
