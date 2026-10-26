// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import { en } from "./en";
import { formatNumber, withUnit } from "./format";
import { ru } from "./ru";

describe("numbers", () => {
  it("follow the interface language", () => {
    expect(formatNumber(4600, "ru-RU")).toBe("4 600");
    expect(formatNumber(4600, "en-US")).toBe("4,600");
    expect(formatNumber(16.94, "ru-RU", 1)).toBe("16,9");
    expect(formatNumber(16.94, "en-US", 1)).toBe("16.9");
  });

  it("keep the unit on the same line", () => {
    expect(withUnit("17", "Вт")).toBe("17 Вт");
  });
});

describe("plural forms", () => {
  it.each([
    [1, "1 изменение · вернуть всё как было"],
    [3, "3 изменения · вернуть всё как было"],
    [5, "5 изменений · вернуть всё как было"],
    [21, "21 изменение · вернуть всё как было"],
    [0, "ORIGAMI ничего не менял"],
  ])("Russian, %i", (count, text) => {
    expect(ru.settings.changesSummary(count)).toBe(text);
  });

  it.each([
    [1, "1 change · restore all"],
    [7, "7 changes · restore all"],
  ])("English, %i", (count, text) => {
    expect(en.settings.changesSummary(count)).toBe(text);
  });
});
