// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { afterEach, describe, expect, it, vi } from "vitest";

import { installQamTab, ORIGAMI_TAB, placeTab, SOUNDTRACKS_TAB, type SteamTab } from "./qamTab";

// Steam's column on the console (2026-10-26): Notifications, Friends, Quick settings,
// Performance, Soundtracks, Help, then Decky.
const steamColumn = () => [0, 3, 4, 5, 7, 6, 999].map((key) => ({ key }));
const keys = (tabs: SteamTab[]) => tabs.map((tab) => tab.key);

/** Behaves like Decky's tabs hook: appends every added tab to Steam's list once. */
function fakeTabsHook() {
  const added: { id: number }[] = [];
  return {
    added,
    add: vi.fn((tab: { id: number }) => added.push(tab)),
    removeById: vi.fn((id: number) => added.splice(added.findIndex((tab) => tab.id === id), 1)),
    render: (existingTabs: SteamTab[]) => {
      for (const tab of added) {
        if (!existingTabs.some((entry) => entry.key === tab.id)) existingTabs.push({ key: tab.id });
      }
    },
  };
}

const content = { title: "ORIGAMI", icon: null, content: null };

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("placeTab", () => {
  it("puts the tab right above Soundtracks", () => {
    const tabs = [...steamColumn(), { key: ORIGAMI_TAB }];

    placeTab(tabs, ORIGAMI_TAB, SOUNDTRACKS_TAB);

    expect(keys(tabs)).toEqual([0, 3, 4, 5, ORIGAMI_TAB, 7, 6, 999]);
  });

  it("is stable on every render", () => {
    const tabs = [0, 3, 4, 5, ORIGAMI_TAB, 7, 6, 999].map((key) => ({ key }));

    placeTab(tabs, ORIGAMI_TAB, SOUNDTRACKS_TAB);

    expect(keys(tabs)).toEqual([0, 3, 4, 5, ORIGAMI_TAB, 7, 6, 999]);
  });

  it("falls back to the end without Soundtracks", () => {
    const tabs = [{ key: ORIGAMI_TAB }, { key: 0 }, { key: 999 }];

    placeTab(tabs, ORIGAMI_TAB, SOUNDTRACKS_TAB);

    expect(keys(tabs)).toEqual([0, 999, ORIGAMI_TAB]);
  });
});

describe("installQamTab", () => {
  it("adds the tab above Soundtracks and removes it without a trace", () => {
    const hook = fakeTabsHook();
    const originalRender = hook.render;
    vi.stubGlobal("window", { DeckyPluginLoader: { tabsHook: hook } });
    const tabs = steamColumn();

    const remove = installQamTab(content, SOUNDTRACKS_TAB);
    hook.render(tabs);

    expect(keys(tabs)).toEqual([0, 3, 4, 5, ORIGAMI_TAB, 7, 6, 999]);

    remove?.();

    expect(keys(tabs)).toEqual(keys(steamColumn()));
    expect(hook.render).toBe(originalRender);
    expect(hook.added).toEqual([]);
  });

  it("keeps a wrapper added after it working", () => {
    const hook = fakeTabsHook();
    vi.stubGlobal("window", { DeckyPluginLoader: { tabsHook: hook } });
    const remove = installQamTab(content, SOUNDTRACKS_TAB);
    const ours = hook.render;
    const theirs = vi.fn(function (this: unknown, existingTabs: SteamTab[]) {
      ours.call(this, existingTabs);
    });
    hook.render = theirs;

    remove?.();
    const tabs = steamColumn();
    hook.render(tabs);

    expect(hook.render).toBe(theirs);
    expect(keys(tabs)).toEqual(keys(steamColumn()));
  });

  it("does nothing when Decky has no tabs hook", () => {
    vi.stubGlobal("window", { DeckyPluginLoader: {} });
    vi.spyOn(console, "warn").mockImplementation(() => undefined);

    expect(installQamTab(content, SOUNDTRACKS_TAB)).toBeNull();
  });
});
