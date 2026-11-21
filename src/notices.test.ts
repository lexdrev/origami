// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { markRead, readNotices, restoreNotices } from "./notices";

/** Steam's localStorage, which the tests run without. */
function memoryStorage(items = new Map<string, string>()) {
  return {
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => {
      items.set(key, value);
    },
  };
}

describe("notices", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", memoryStorage());
    restoreNotices();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("are unread until their screen has shown them", () => {
    expect(readNotices.get()).toEqual([]);

    markRead("sharpness:Frame Plugin");
    markRead("sharpness:Frame Plugin");

    expect(readNotices.get()).toEqual(["sharpness:Frame Plugin"]);
  });

  it("stay read after Steam restarts", () => {
    markRead("sharpness:Frame Plugin");
    markRead("sharpness:launch options");
    readNotices.set([]);

    restoreNotices();

    expect(readNotices.get()).toEqual(["sharpness:Frame Plugin", "sharpness:launch options"]);
  });

  it("are taken from a saved list only, and only its names", () => {
    for (const text of ["{broken", '{"read": true}', '["sharpness:launch options", 7]']) {
      vi.stubGlobal("localStorage", memoryStorage(new Map([["origami.notices", text]])));
      restoreNotices();
      expect(readNotices.get()).toEqual(text.startsWith("[") ? ["sharpness:launch options"] : []);
    }
  });
});
