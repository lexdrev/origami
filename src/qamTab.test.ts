// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { installQamTab, ORIGAMI_TAB, placeTab, SOUNDTRACKS_TAB, type SteamTab } from "./qamTab";

type TreeHandler = (args: unknown[], tree: unknown) => unknown;

// Stand-ins for the parts of @decky/ui that only work inside Steam.
const decky = vi.hoisted(() => ({
  unpatch: vi.fn(),
  menuHandler: null as TreeHandler | null,
  renderer: { type: () => "QuickAccessMenuBrowserView" },
}));

vi.mock("@decky/ui", () => ({
  afterPatch: vi.fn(() => ({ unpatch: decky.unpatch })),
  createReactTreePatcher: vi.fn((_steps: unknown, handler: TreeHandler) => {
    decky.menuHandler = handler;
    return handler;
  }),
  findInReactTree: (tree: { props?: unknown } | null, filter: (node: unknown) => boolean) =>
    tree !== null && filter(tree) ? tree : undefined,
  findModuleByExport: () => ({ renderer: decky.renderer }),
  getReactRoot: () => null,
}));

// Steam's column on the console (2026-10-26): Notifications, Friends, Quick settings,
// Performance, Soundtracks, Help, then Decky.
const steamColumn = () => [0, 3, 4, 5, 7, 6, 999].map((key) => ({ key }));
const keys = (tabs: SteamTab[]) => tabs.map((tab) => tab.key);
const content = { title: "ORIGAMI", icon: null, content: null };

/** Like Decky's tabs hook: keeps added tabs, which Decky appends to Steam's list on render. */
function fakeTabsHook() {
  const added: { id: number }[] = [];
  return {
    added,
    add: vi.fn((tab: { id: number }) => added.push(tab)),
    removeById: vi.fn((id: number) => added.splice(added.findIndex((tab) => tab.id === id), 1)),
  };
}

/** One render of the menu: Decky appends its tabs, then ORIGAMI's patch runs. */
function renderMenu(tabs: SteamTab[], hook: ReturnType<typeof fakeTabsHook>) {
  for (const tab of hook.added) {
    if (!tabs.some((entry) => entry.key === tab.id)) tabs.push({ key: tab.id });
  }
  decky.menuHandler?.([], { props: { tabs } });
}

beforeEach(() => {
  vi.stubGlobal("document", { getElementById: () => null });
});

afterEach(() => {
  vi.unstubAllGlobals();
  decky.unpatch.mockClear();
  decky.menuHandler = null;
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
    vi.stubGlobal("window", { DeckyPluginLoader: { tabsHook: hook } });
    const tabs = steamColumn();

    const remove = installQamTab(content, SOUNDTRACKS_TAB);
    renderMenu(tabs, hook);

    expect(hook.add).toHaveBeenCalledWith(expect.objectContaining({ id: ORIGAMI_TAB, title: "ORIGAMI" }));
    expect(keys(tabs)).toEqual([0, 3, 4, 5, ORIGAMI_TAB, 7, 6, 999]);

    remove?.();

    expect(decky.unpatch).toHaveBeenCalled();
    expect(hook.added).toEqual([]);
    expect(keys(tabs)).toEqual(keys(steamColumn()));
  });

  it("leaves Decky's tabs hook itself untouched", () => {
    const hook = fakeTabsHook();
    const methods = { ...hook };
    vi.stubGlobal("window", { DeckyPluginLoader: { tabsHook: hook } });

    installQamTab(content, SOUNDTRACKS_TAB);

    expect(hook).toEqual(methods);
  });

  it("does nothing when Decky has no tabs hook", () => {
    vi.stubGlobal("window", { DeckyPluginLoader: {} });
    vi.spyOn(console, "warn").mockImplementation(() => undefined);

    expect(installQamTab(content, SOUNDTRACKS_TAB)).toBeNull();
  });
});
