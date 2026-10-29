// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import { en } from "./i18n/en";
import { ru } from "./i18n/ru";
import { FIRST_TAB, ownTabIndex, ownTabSummary, positionAt, tabName } from "./tabPosition";

// Steam's column on the console with another plugin's tab in it (2026-10-26).
const column = [
  { key: 5260355, title: "Панель управления" },
  ...[0, 3, 4, 5, 7, 6, 999].map((key) => ({ key, title: null })),
];

describe("ORIGAMI's place in the column", () => {
  it("stands above Soundtracks by default", () => {
    expect(ownTabIndex(column, 7)).toBe(5);
  });

  it("goes on top, to the end, and to the end when its neighbour is gone", () => {
    expect(ownTabIndex(column, FIRST_TAB)).toBe(0);
    expect(ownTabIndex(column, null)).toBe(column.length);
    expect(ownTabIndex(column, 1)).toBe(column.length);
  });

  it("stores the top as the top, not as the tab that is there now", () => {
    expect(positionAt(column, 0)).toBe(FIRST_TAB);
    expect(positionAt(column, 5)).toBe(7);
    expect(positionAt(column, column.length)).toBeNull();
  });

  it("moves one step up and down", () => {
    const index = ownTabIndex(column, 7);

    expect(ownTabIndex(column, positionAt(column, index - 1))).toBe(index - 1);
    expect(ownTabIndex(column, positionAt(column, index + 1))).toBe(index + 1);
  });
});

describe("tab names", () => {
  it("name Steam's tabs by key and other plugins by their title", () => {
    expect(tabName({ key: 7, title: null }, ru)).toBe("Саундтреки");
    expect(tabName({ key: 5260355, title: "Панель управления" }, ru)).toBe("Панель управления");
    expect(tabName({ key: 123, title: null }, en)).toBe("Plugin");
  });
});

describe("summary in the settings", () => {
  it.each([
    [true, 7, "Вкл · над вкладкой «Саундтреки»"],
    [true, FIRST_TAB, "Вкл · первая в колонке"],
    [true, null, "Вкл · последняя в колонке"],
    [false, 7, "Выкл · только внутри Decky"],
  ] as const)("enabled %s, before %s", (enabled, position, text) => {
    expect(ownTabSummary(enabled, position, { tabs: column, arranger: null }, ru)).toBe(text);
  });

  it("names the plugin that arranges the column, when it is known", () => {
    const known = ownTabSummary(true, 7, { tabs: column, arranger: { name: "Tabs Plugin" } }, ru);
    const unknown = ownTabSummary(true, 7, { tabs: column, arranger: { name: null } }, ru);

    expect(known).toBe("Вкл · место задаёт Tabs Plugin");
    expect(unknown).toBe("Вкл · место задаёт другой плагин");
  });
});
