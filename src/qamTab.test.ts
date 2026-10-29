// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createOwnTab, KNOWN_ARRANGERS, placeTab, repairDeckyTabs } from "./qamTab";
import { ORIGAMI_TAB } from "./quickAccess";
import type { Store } from "./store";
import { FIRST_TAB, quickAccessColumn } from "./tabPosition";

type TreeHandler = (args: unknown[], tree: unknown) => unknown;
interface Entry {
  key: number;
  title?: unknown;
  decky?: boolean;
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

// The column is rendered by calling it, outside React, so its store hook just reads the store.
vi.mock("./store", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./store")>()),
  useStore: <T,>(store: Store<T>) => store.get(),
}));

const SOUNDTRACKS = 7;
const DECKY_TAB = 999;
// Steam's column on the console (2026-10-26): Notifications, Friends, Quick settings,
// Performance, Soundtracks, Help, then Decky's tab.
const steamColumn = (): Entry[] => [
  ...[0, 3, 4, 5, 7, 6].map((key) => ({ key })),
  { key: DECKY_TAB, decky: true },
];
const keys = (tabs: Entry[]) => tabs.map((tab) => tab.key);
const content = { title: null, icon: null, content: null };

/** Decky's tabs hook: its render is on the prototype and only counts Decky's entries. */
class DeckyTabsHook {
  tabs: { id: number }[] = [{ id: DECKY_TAB }];

  add(tab: { id: number }) {
    this.tabs.push(tab);
  }

  removeById(id: number) {
    this.tabs = this.tabs.filter((tab) => tab.id !== id);
  }

  render(existing: Entry[]) {
    if (existing.filter((tab) => tab.decky).length === this.tabs.length) return;
    for (const { id } of this.tabs) existing.push({ key: id, decky: true });
  }
}

/**
 * Decky's hook with its render replaced by another plugin's reconciler, which keeps Decky's
 * entries in line with the list and, like the known ones, fails for good once anyone else
 * has changed them since its last render.
 */
function reconcilingHook() {
  const hook = new DeckyTabsHook();
  const state = { failed: false, rendered: [] as number[] };
  hook.render = function (existing: Entry[]) {
    const deckyKeys = keys(existing.filter((tab) => tab.decky)).sort();
    if (state.failed || (state.rendered.length > 0 && deckyKeys.join() !== state.rendered.join())) {
      state.failed = true;
      return;
    }
    const native = existing.filter((tab) => !tab.decky);
    existing.splice(0, existing.length, ...native, ...this.tabs.map(({ id }) => ({ key: id, decky: true })));
    state.rendered = this.tabs.map(({ id }) => id).sort();
  };
  return { hook, state };
}

function setUp(hook: DeckyTabsHook = new DeckyTabsHook()) {
  vi.stubGlobal("window", { DeckyPluginLoader: { tabsHook: hook } });
  return { hook, ownTab: createOwnTab(content) };
}

interface ColumnElement {
  type: unknown;
  props: Record<string, unknown>;
}

function SteamColumn() {
  return null;
}

/** Renders the column as React would: the wrapped component is called with its props. */
function renderColumn(column: ColumnElement) {
  const render = column.type as (props: Record<string, unknown>) => unknown;
  render(column.props);
}

/** One render of the menu: Decky's patch fills the list, then ORIGAMI's runs and the column renders. */
function renderMenu(tabs: Entry[], hook: DeckyTabsHook): ColumnElement {
  hook.render(tabs);
  const column: ColumnElement = { type: SteamColumn, props: { tabs, activeTab: 0 } };
  decky.menuHandler?.([{ visible: true }], column);
  renderColumn(column);
  return column;
}

beforeEach(() => {
  vi.stubGlobal("document", { getElementById: () => null });
});

afterEach(() => {
  vi.unstubAllGlobals();
  decky.unpatch.mockClear();
  decky.menuHandler = null;
  quickAccessColumn.set({ tabs: [], arranger: null });
});

describe("placeTab", () => {
  it("puts the tab right above Soundtracks", () => {
    const tabs = [...steamColumn(), { key: ORIGAMI_TAB }];

    placeTab(tabs, ORIGAMI_TAB, SOUNDTRACKS);

    expect(keys(tabs)).toEqual([0, 3, 4, 5, ORIGAMI_TAB, 7, 6, DECKY_TAB]);
  });

  it("puts the tab on top or at the end", () => {
    const tabs = [...steamColumn(), { key: ORIGAMI_TAB }];

    placeTab(tabs, ORIGAMI_TAB, FIRST_TAB);
    expect(keys(tabs)[0]).toBe(ORIGAMI_TAB);

    placeTab(tabs, ORIGAMI_TAB, null);
    expect(keys(tabs).at(-1)).toBe(ORIGAMI_TAB);
  });

  it("falls back to the end when its neighbour is gone", () => {
    const tabs = [{ key: ORIGAMI_TAB }, { key: 0 }, { key: DECKY_TAB }];

    placeTab(tabs, ORIGAMI_TAB, SOUNDTRACKS);

    expect(keys(tabs)).toEqual([0, DECKY_TAB, ORIGAMI_TAB]);
  });
});

describe("repairDeckyTabs", () => {
  it("drops the copies Decky appends when a tab is added to a filled list", () => {
    const deckyTab = { key: DECKY_TAB, decky: true };
    const tabs = [{ key: 0 }, deckyTab, { key: DECKY_TAB, decky: true }, { key: ORIGAMI_TAB, decky: true }];

    repairDeckyTabs(tabs, new Set([DECKY_TAB, ORIGAMI_TAB]));

    expect(keys(tabs)).toEqual([0, DECKY_TAB, ORIGAMI_TAB]);
    expect(tabs[1]).toBe(deckyTab);
  });

  it("takes ORIGAMI's entry out once it is no longer registered", () => {
    const tabs = [{ key: 0 }, { key: DECKY_TAB, decky: true }, { key: ORIGAMI_TAB, decky: true }];

    repairDeckyTabs(tabs, new Set([DECKY_TAB]));

    expect(keys(tabs)).toEqual([0, DECKY_TAB]);
  });

  it("leaves entries Decky does not know about alone", () => {
    const tabs = [{ key: 0 }, { key: 42, decky: true }, { key: DECKY_TAB, decky: true }];

    repairDeckyTabs(tabs, new Set([DECKY_TAB]));

    expect(keys(tabs)).toEqual([0, 42, DECKY_TAB]);
  });
});

describe("ORIGAMI's own tab with Decky's own render", () => {
  it("appears above Soundtracks without a second Decky tab", () => {
    const { hook, ownTab } = setUp();
    const tabs = steamColumn();
    renderMenu(tabs, hook);

    ownTab?.apply(true, SOUNDTRACKS);
    renderMenu(tabs, hook);

    expect(keys(tabs)).toEqual([0, 3, 4, 5, ORIGAMI_TAB, 7, 6, DECKY_TAB]);
  });

  it("moves at once, without waiting for the menu to render", () => {
    const { hook, ownTab } = setUp();
    const tabs = steamColumn();
    ownTab?.apply(true, SOUNDTRACKS);
    const column = renderMenu(tabs, hook);

    ownTab?.apply(true, FIRST_TAB);
    renderColumn(column);

    expect(keys(tabs)).toEqual([ORIGAMI_TAB, 0, 3, 4, 5, 7, 6, DECKY_TAB]);
  });

  it("is hidden and comes back", () => {
    const { hook, ownTab } = setUp();
    const tabs = steamColumn();
    ownTab?.apply(true, SOUNDTRACKS);
    const column = renderMenu(tabs, hook);

    ownTab?.apply(false, SOUNDTRACKS);
    renderColumn(column);
    expect(keys(tabs)).toEqual(keys(steamColumn()));

    ownTab?.apply(true, SOUNDTRACKS);
    renderColumn(column);
    expect(keys(tabs)).toEqual([0, 3, 4, 5, ORIGAMI_TAB, 7, 6, DECKY_TAB]);

    renderMenu(tabs, hook);
    expect(keys(tabs)).toEqual([0, 3, 4, 5, ORIGAMI_TAB, 7, 6, DECKY_TAB]);
  });

  it("leaves the list as Decky expects it when the plugin unloads", () => {
    const { hook, ownTab } = setUp();
    const tabs = steamColumn();
    ownTab?.apply(true, SOUNDTRACKS);
    renderMenu(tabs, hook);

    ownTab?.dispose();
    hook.render(tabs);

    expect(decky.unpatch).toHaveBeenCalled();
    expect(hook.tabs).toEqual([{ id: DECKY_TAB }]);
    expect(keys(tabs)).toEqual(keys(steamColumn()));
  });

  it("tells the settings screen what the column looks like", async () => {
    const { hook, ownTab } = setUp();
    const tabs: Entry[] = [{ key: 5260355, title: "Панель управления" }, ...steamColumn()];
    ownTab?.apply(true, SOUNDTRACKS);

    renderMenu(tabs, hook);
    await Promise.resolve();

    expect(quickAccessColumn.get()).toEqual({
      tabs: [
        { key: 5260355, title: "Панель управления" },
        ...keys(steamColumn()).map((key) => ({ key, title: null })),
      ],
      arranger: null,
    });
  });

  it("keeps Decky's render in place", () => {
    const { hook, ownTab } = setUp();

    ownTab?.apply(true, SOUNDTRACKS);
    renderMenu(steamColumn(), hook);

    expect(Object.hasOwn(hook, "render")).toBe(false);
  });
});

describe("ORIGAMI's own tab when another plugin replaced Decky's render", () => {
  it("is shown, hidden and shown again by that plugin, which never fails", () => {
    const { hook, state } = reconcilingHook();
    const { ownTab } = setUp(hook);
    const tabs = steamColumn();
    ownTab?.apply(true, SOUNDTRACKS);
    const column = renderMenu(tabs, hook);
    expect(keys(tabs)).toContain(ORIGAMI_TAB);

    ownTab?.apply(false, SOUNDTRACKS);
    renderColumn(column);
    expect(keys(tabs)).not.toContain(ORIGAMI_TAB);

    ownTab?.apply(true, SOUNDTRACKS);
    renderColumn(column);
    renderMenu(tabs, hook);

    expect(keys(tabs)).toContain(ORIGAMI_TAB);
    expect(state.failed).toBe(false);
  });

  it("leaves the order to that plugin and says so", async () => {
    const { hook } = reconcilingHook();
    const { ownTab } = setUp(hook);
    const tabs = steamColumn();
    ownTab?.apply(true, FIRST_TAB);

    renderMenu(tabs, hook);
    await Promise.resolve();

    expect(keys(tabs)).toEqual([...keys(steamColumn()), ORIGAMI_TAB]);
    expect(quickAccessColumn.get().arranger).toEqual({ name: null });
  });

  it.each(KNOWN_ARRANGERS)("names $name by the mark it leaves on Decky's hook", async (known) => {
    const { hook } = reconcilingHook();
    Object.defineProperty(hook, known.marker, { value: {} });
    setUp(hook);

    renderMenu(steamColumn(), hook);
    await Promise.resolve();

    expect(quickAccessColumn.get().arranger).toEqual({ name: known.name });
  });

  it("leaves taking its entry out to that plugin when the plugin unloads", () => {
    const { hook, state } = reconcilingHook();
    const { ownTab } = setUp(hook);
    const tabs = steamColumn();
    ownTab?.apply(true, SOUNDTRACKS);
    renderMenu(tabs, hook);

    ownTab?.dispose();
    hook.render(tabs);

    expect(keys(tabs)).toEqual(keys(steamColumn()));
    expect(state.failed).toBe(false);
  });
});

describe("without Decky's tabs hook", () => {
  it("there is no own tab", () => {
    vi.stubGlobal("window", { DeckyPluginLoader: {} });
    vi.spyOn(console, "warn").mockImplementation(() => undefined);

    expect(createOwnTab(content)).toBeNull();
  });
});
