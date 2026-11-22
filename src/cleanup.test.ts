// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import type { CleanupItem } from "./backend";
import {
  formatSize,
  installedCaches,
  itemNote,
  itemTitle,
  leftovers,
  mayLoseSaves,
  pickedSize,
  safeToRemove,
} from "./cleanup";
import { en } from "./i18n/en";
import { ru } from "./i18n/ru";

const NBSP = " ";
const MB = 2 ** 20;
const GB = 2 ** 30;

function item(kind: CleanupItem["kind"], owner: CleanupItem["owner"], more: Partial<CleanupItem> = {}): CleanupItem {
  const appId = kind === "folder" ? null : 617290;
  return {
    key: `${kind}:0:${owner}`,
    kind,
    owner,
    appId,
    name: kind === "folder" ? "Remnant" : null,
    size: GB,
    userSize: null,
    hints: [],
    busy: false,
    ...more,
  };
}

const cache = item("shaders", "installed", { name: "Installed Game", size: 2 * GB });
const leftCache = item("shaders", "removed");
const prefix = item("prefix", "removed", { hints: ["Remnant"] });
const shortcut = item("prefix", "shortcut", { appId: 3293947715, hints: ["BB3", "Saves"] });
const folder = item("folder", "removed");
const all = [cache, leftCache, prefix, shortcut, folder];

describe("sizes", () => {
  it("are in Steam's binary units, finer while small", () => {
    expect(formatSize(1.584 * GB, ru)).toBe(`1,58${NBSP}ГБ`);
    expect(formatSize(41.44 * GB, en)).toBe(`41.4${NBSP}GB`);
    expect(formatSize(191.44 * GB, en)).toBe(`191${NBSP}GB`);
    expect(formatSize(319.6 * MB, ru)).toBe(`320${NBSP}МБ`);
    expect(formatSize(300_000, en)).toBe(`under 1${NBSP}MB`);
    expect(formatSize(0, ru)).toBe(`меньше 1${NBSP}МБ`);
  });

  it("add up for what is picked", () => {
    expect(pickedSize(all, new Set([cache.key, folder.key, "gone"]))).toBe(3 * GB);
    expect(pickedSize(all, new Set())).toBe(0);
  });
});

describe("the lists", () => {
  it("part what removed games left from the caches of the installed", () => {
    expect(leftovers(all)).toEqual([leftCache, prefix, shortcut, folder]);
    // The game folders come after what has a game to name, whatever their size.
    expect(leftovers([folder, cache, shortcut, leftCache])).toEqual([shortcut, leftCache, folder]);
    expect(installedCaches(all)).toEqual([cache]);
  });
});

describe("saves", () => {
  it("are at stake in a prefix Steam's cloud does not keep, and in a folder left behind", () => {
    expect(mayLoseSaves(cache, "unknown")).toBe(false);
    expect(mayLoseSaves(leftCache, "local")).toBe(false);
    expect(mayLoseSaves(prefix, "cloud")).toBe(false);
    expect(mayLoseSaves(prefix, "local")).toBe(true);
    expect(mayLoseSaves(prefix, "unknown")).toBe(true);
    // Steam has no cloud for a non-Steam game, whatever is said of its number.
    expect(mayLoseSaves(shortcut, "cloud")).toBe(true);
    expect(mayLoseSaves(folder, "cloud")).toBe(true);
  });

  it("are safe in what the one button picks", () => {
    expect(safeToRemove(all, {})).toEqual([leftCache.key]);
    expect(safeToRemove(all, { 617290: "cloud" })).toEqual([leftCache.key, prefix.key]);
    expect(safeToRemove(all, { 617290: "local" })).toEqual([leftCache.key]);
    // What Steam works with now is not picked, nor is an installed game's cache.
    expect(safeToRemove([cache, { ...leftCache, busy: true }], {})).toEqual([]);
  });
});

describe("a row", () => {
  it("is named by the backend, else by Steam, else by the game's number", () => {
    expect(itemTitle(cache, "Other Name", ru)).toBe("Installed Game");
    expect(itemTitle(folder, null, ru)).toBe("Remnant");
    expect(itemTitle(prefix, "Remnant: From the Ashes", ru)).toBe("Remnant: From the Ashes");
    expect(itemTitle(prefix, null, ru)).toBe("Игра 617290");
    expect(itemTitle(shortcut, null, en)).toBe("Removed shortcut 3293947715");
  });

  it("says where the saves are", () => {
    expect(itemNote(leftCache, "unknown", true, ru)).toBeNull();
    expect(itemNote(prefix, "cloud", true, ru)).toEqual({ text: `Сохранения есть в${NBSP}Steam Cloud`, danger: false });
    expect(itemNote(prefix, "local", true, en)).toEqual({ text: "No Steam Cloud · the saves go", danger: true });
    expect(itemNote(prefix, "unknown", true, en)?.danger).toBe(true);
    expect(itemNote(folder, "unknown", true, en)).toEqual({ text: "May hold saves and mods", danger: true });
  });

  it("tells a game nothing names by the folders in its prefix", () => {
    expect(itemNote(shortcut, "unknown", false, en)).toEqual({
      text: "A non-Steam game · saves and launcher logins go · inside: BB3, Saves",
      danger: true,
    });
    expect(itemNote(prefix, "local", false, en)?.text).toBe("No Steam Cloud · the saves go · inside: Remnant");
    expect(itemNote(prefix, "local", true, en)?.text).toBe("No Steam Cloud · the saves go");
  });

  it("says why it cannot be picked while Steam works with the game", () => {
    expect(itemNote({ ...prefix, busy: true }, "local", true, en)).toEqual({
      text: "Steam works with this game now",
      danger: false,
    });
  });
});
