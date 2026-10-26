// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createOwnTab, ORIGAMI_TAB, placeTab } from "./qamTab";
import { FIRST_TAB, quickAccessColumn } from "./tabPosition";

type TreeHandler = (args: unknown[], tree: unknown) => unknown;
interface Entry {
  key: number;
  title?: unknown;
}

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

const SOUNDTRACKS = 7;
// Steam's column on the console (2026-10-26): Notifications, Friends, Quick settings,
// Performance, Soundtracks, Help, then Decky.
const steamColumn = (): Entry[] => [0, 3, 4, 5, 7, 6, 999].map((key) => ({ key }));
const keys = (tabs: Entry[]) => tabs.map((tab) => tab.key);
const content = { title: null, icon: null, content: null };

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
function renderMenu(tabs: Entry[], hook: ReturnType<typeof fakeTabsHook>) {
  for (const tab of hook.added) {
    if (!tabs.some((entry) => entry.key === tab.id)) tabs.push({ key: tab.id });
  }
  decky.menuHandler?.([], { props: { tabs } });
}

function setUp() {
  const hook = fakeTabsHook();
  vi.stubGlobal("window", { DeckyPluginLoader: { tabsHook: hook } });
  return { hook, ownTab: createOwnTab(content) };
}

beforeEach(() => {
  vi.stubGlobal("document", { getElementById: () => null });
});

afterEach(() => {
  vi.unstubAllGlobals();
  decky.unpatch.mockClear();
  decky.menuHandler = null;
  quickAccessColumn.set([]);
});

describe("placeTab", () => {
  it("puts the tab right above Soundtracks", () => {
    const tabs = [...steamColumn(), { key: ORIGAMI_TAB }];

    placeTab(tabs, ORIGAMI_TAB, SOUNDTRACKS);

    expect(keys(tabs)).toEqual([0, 3, 4, 5, ORIGAMI_TAB, 7, 6, 999]);
  });

  it("puts the tab on top or at the end", () => {
    const tabs = [...steamColumn(), { key: ORIGAMI_TAB }];

    placeTab(tabs, ORIGAMI_TAB, FIRST_TAB);
    expect(keys(tabs)[0]).toBe(ORIGAMI_TAB);

    placeTab(tabs, ORIGAMI_TAB, null);
    expect(keys(tabs).at(-1)).toBe(ORIGAMI_TAB);
  });

  it("falls back to the end when its neighbour is gone", () => {
    const tabs = [{ key: ORIGAMI_TAB }, { key: 0 }, { key: 999 }];

    placeTab(tabs, ORIGAMI_TAB, SOUNDTRACKS);

    expect(keys(tabs)).toEqual([0, 999, ORIGAMI_TAB]);
  });
});

describe("ORIGAMI's own tab", () => {
  it("appears above Soundtracks and moves without waiting for a redraw", () => {
    const { hook, ownTab } = setUp();
    const tabs = steamColumn();

    ownTab?.apply(true, SOUNDTRACKS);
    renderMenu(tabs, hook);
    expect(keys(tabs)).toEqual([0, 3, 4, 5, ORIGAMI_TAB, 7, 6, 999]);

    ownTab?.apply(true, FIRST_TAB);
    expect(keys(tabs)).toEqual([ORIGAMI_TAB, 0, 3, 4, 5, 7, 6, 999]);
  });

  it("is hidden and removed without a trace", () => {
    const { hook, ownTab } = setUp();
    const tabs = steamColumn();
    ownTab?.apply(true, SOUNDTRACKS);
    renderMenu(tabs, hook);

    ownTab?.apply(false, SOUNDTRACKS);

    expect(hook.added).toEqual([]);
    expect(keys(tabs)).toEqual(keys(steamColumn()));

    ownTab?.dispose();
    expect(decky.unpatch).toHaveBeenCalled();
  });

  it("tells the settings screen what the column looks like", async () => {
    const { hook, ownTab } = setUp();
    const tabs: Entry[] = [{ key: 5260355, title: "Панель управления" }, ...steamColumn()];
    ownTab?.apply(true, SOUNDTRACKS);

    renderMenu(tabs, hook);
    await Promise.resolve();

    expect(quickAccessColumn.get()).toEqual([
      { key: 5260355, title: "Панель управления" },
      ...keys(steamColumn()).map((key) => ({ key, title: null })),
    ]);
  });

  it("leaves Decky's tabs hook itself untouched", () => {
    const hook = fakeTabsHook();
    const methods = { ...hook };
    vi.stubGlobal("window", { DeckyPluginLoader: { tabsHook: hook } });

    createOwnTab(content);

    expect(hook).toEqual(methods);
  });

  it("is not created when Decky has no tabs hook", () => {
    vi.stubGlobal("window", { DeckyPluginLoader: {} });
    vi.spyOn(console, "warn").mockImplementation(() => undefined);

    expect(createOwnTab(content)).toBeNull();
  });
});
