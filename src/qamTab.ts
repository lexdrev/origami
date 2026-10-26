// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import {
  afterPatch,
  createReactTreePatcher,
  findInReactTree,
  findModuleByExport,
  getReactRoot,
  type Patch,
} from "@decky/ui";
import { createElement, type ElementType, type ReactNode } from "react";

import { ORIGAMI_TAB } from "./quickAccess";
import { createStore, useStore } from "./store";
import { FIRST_TAB, quickAccessColumn, type Arranger, type TabPosition } from "./tabPosition";

/** Entry of Steam's quick access tab list; Decky marks the entries it adds with `decky`. */
interface SteamTab {
  key: number;
  title?: unknown;
  decky?: boolean;
}

export interface TabContent {
  title: ReactNode;
  icon: ReactNode;
  content: ReactNode;
}

export interface OwnTab {
  /** Shows or hides ORIGAMI's tab and moves it to `position`. */
  apply: (enabled: boolean, position: TabPosition) => void;
  /** Whether ORIGAMI's tab is in the column now. */
  shown: () => boolean;
  dispose: () => void;
}

// Decky's tabs hook (decky-loader frontend/src/tabs-hook.tsx, v3.3.0) keeps the list of plugin
// tabs and, whenever the menu renders, adds them to Steam's list with its error boundary and the
// visibility state @decky/api reads. Steam memoizes that list, and Decky's render only counts its
// own entries in it: when the count is off it appends every tab again, and it never takes one out.
// Plugins that change tabs at runtime (Panel de Control) replace the render with a reconciler of
// their own, which fails once anyone else edits Decky's entries. ORIGAMI never replaces the render
// and edits Decky's entries only while Decky's own render is in place.
interface DeckyTabsHook {
  tabs: readonly { id: number }[];
  add: (tab: TabContent & { id: number }) => void;
  removeById: (id: number) => void;
  render: (tabs: SteamTab[], visible: boolean) => void;
}

declare global {
  interface Window {
    DeckyPluginLoader?: { tabsHook?: unknown; deckyState?: unknown };
  }
}

function isTabsHook(value: unknown): value is DeckyTabsHook {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return (
    Array.isArray(candidate.tabs) &&
    typeof candidate.add === "function" &&
    typeof candidate.removeById === "function" &&
    typeof candidate.render === "function"
  );
}

/** Whether Decky's own render fills Steam's list rather than another plugin's replacement. */
function deckyRendersTabs(hook: DeckyTabsHook): boolean {
  const prototype: unknown = Object.getPrototypeOf(hook);
  return (
    typeof prototype === "object" && prototype !== null && "render" in prototype && prototype.render === hook.render
  );
}

// Plugins known to replace Decky's render, by the global symbol each leaves on the hook while its
// replacement is in place, with their names as Decky lists them.
const KNOWN_ARRANGERS = [{ marker: Symbol.for("panel-de-control.qam-render-adapter"), name: "Panel de Control" }];

/** The plugin that arranges the column, or null when Decky's own render is in place. */
function arrangerOf(hook: DeckyTabsHook): Arranger | null {
  if (deckyRendersTabs(hook)) return null;
  return { name: KNOWN_ARRANGERS.find(({ marker }) => marker in hook)?.name ?? null };
}

const isOwnTab = (tab: SteamTab) => tab.key === ORIGAMI_TAB;

/** Moves the tab `key` to `position`; a position before a tab that is not there means the end. */
export function placeTab(tabs: SteamTab[], key: number, position: TabPosition): void {
  const from = tabs.findIndex((tab) => tab.key === key);
  if (from < 0) return;
  const [moved] = tabs.splice(from, 1);
  if (moved === undefined) return;
  const anchor = position === FIRST_TAB ? 0 : tabs.findIndex((tab) => tab.key === position);
  tabs.splice(anchor < 0 ? tabs.length : anchor, 0, moved);
}

/**
 * Undoes what Decky's own render does to a list it filled before a tab was added or removed:
 * the first entry of each registered tab stays (its panel is the mounted one), the copies appended
 * after it go, and so does ORIGAMI's entry once ORIGAMI is no longer registered. Entries Decky
 * does not know about are left alone.
 */
export function repairDeckyTabs(tabs: SteamTab[], registered: ReadonlySet<number>): void {
  const seen = new Set<number>();
  const kept = tabs.filter((tab) => {
    if (tab.decky !== true) return true;
    if (isOwnTab(tab) && !registered.has(ORIGAMI_TAB)) return false;
    if (!registered.has(tab.key)) return true;
    if (seen.has(tab.key)) return false;
    seen.add(tab.key);
    return true;
  });
  if (kept.length !== tabs.length) tabs.splice(0, tabs.length, ...kept);
}

function propsOf(node: unknown): Record<string, unknown> | undefined {
  if (typeof node !== "object" || node === null || !("props" in node)) return undefined;
  const props = node.props;
  return typeof props === "object" && props !== null ? (props as Record<string, unknown>) : undefined;
}

interface ReactElementLike {
  type: unknown;
  props: Record<string, unknown>;
}

function isElement(node: unknown): node is ReactElementLike {
  return typeof node === "object" && node !== null && "type" in node && propsOf(node) !== undefined;
}

function isComponent(value: unknown): value is ElementType {
  return typeof value === "function" || (typeof value === "object" && value !== null);
}

function componentSource(value: unknown): string {
  if (typeof value !== "object" || value === null || !("type" in value)) return "";
  // The function's own toString on purpose: Decky has already patched the menu, and its patcher
  // makes the wrapper report the original component's source.
  return typeof value.type === "function" ? value.type.toString() : "";
}

/** Steam renders the menu in a browser view and an embedded variant; Decky patches both. */
function quickAccessRenderers(): object[] {
  const isRenderer = (value: unknown) => /QuickAccessMenu(BrowserView|Embedded)/.test(componentSource(value));
  const module: unknown = findModuleByExport(isRenderer);
  if (typeof module !== "object" || module === null) return [];
  return Object.values(module).filter((value): value is object => isRenderer(value));
}

interface Fiber {
  elementType: unknown;
  type: unknown;
  alternate: Fiber | null;
}

function isFiber(value: unknown): value is Fiber {
  return typeof value === "object" && value !== null && "elementType" in value && "type" in value;
}

/** A menu already on screen keeps the component it was created with; point it at the patched one. */
function refreshMountedMenu(renderers: object[]): void {
  const container = document.getElementById("root");
  if (container === null) return;
  const node: unknown = findInReactTree(getReactRoot(container), (candidate: Fiber | null) =>
    renderers.includes(candidate?.elementType as object),
  );
  if (!isFiber(node)) return;
  node.type = (node.elementType as { type: unknown }).type;
  if (node.alternate) node.alternate.type = node.type;
}

const sameArranger = (a: Arranger | null, b: Arranger | null) =>
  a === null || b === null ? a === b : a.name === b.name;

function publishColumn(tabs: SteamTab[], arranger: Arranger | null): void {
  const column = tabs
    .filter((tab) => !isOwnTab(tab))
    .map((tab) => ({ key: tab.key, title: typeof tab.title === "string" ? tab.title : null }));
  const current = quickAccessColumn.get();
  const changed =
    !sameArranger(arranger, current.arranger) ||
    column.length !== current.tabs.length ||
    column.some((tab, i) => tab.key !== current.tabs[i]?.key);
  // The menu is rendering right now; the settings screen re-renders after it, not inside it.
  if (changed) {
    queueMicrotask(() => {
      quickAccessColumn.set({ tabs: column, arranger });
    });
  }
}

/** Prop under which the wrapped column keeps Steam's component and the menu's visibility. */
const OWN_COLUMN = "origamiColumn";

interface ColumnStash {
  column: ElementType;
  visible: boolean;
}

interface OwnColumnProps {
  tabs: SteamTab[];
  [OWN_COLUMN]: ColumnStash;
  [prop: string]: unknown;
}

interface Placement {
  enabled: boolean;
  position: TabPosition;
}

/**
 * Prepares ORIGAMI's own tab in the quick access menu. Returns null when the menu cannot be
 * extended; ORIGAMI then lives only inside the Decky tab.
 */
export function createOwnTab(tab: TabContent): OwnTab | null {
  const hook = window.DeckyPluginLoader?.tabsHook;
  const renderers = quickAccessRenderers();
  if (!isTabsHook(hook) || renderers.length === 0) {
    console.warn("ORIGAMI: the quick access menu cannot be extended; ORIGAMI stays inside the Decky tab");
    return null;
  }

  const placement = createStore<Placement>({ enabled: false, position: null });
  // Lists Steam has given the menu that still hold ORIGAMI's entry; dispose takes it out of them.
  const columns = new Set<SteamTab[]>();
  const registered = () => hook.tabs.some((entry) => entry.id === ORIGAMI_TAB);

  const arrange = (tabs: SteamTab[], visible: boolean) => {
    // Decky adds tabs to Steam's list only while the menu renders, so a change made since then
    // is handed to it, or to the plugin that replaced its render, here.
    if (registered() !== tabs.some(isOwnTab)) hook.render(tabs, visible);
    const arranger = arrangerOf(hook);
    if (arranger === null) {
      repairDeckyTabs(tabs, new Set(hook.tabs.map((entry) => entry.id)));
      placeTab(tabs, ORIGAMI_TAB, placement.get().position);
    }
    for (const known of columns) if (!known.some(isOwnTab)) columns.delete(known);
    if (tabs.some(isOwnTab)) columns.add(tabs);
    publishColumn(tabs, arranger);
  };

  // Steam's tab column, re-rendered on its own when ORIGAMI's tab is switched or moved, so the
  // change shows at once instead of on the menu's next render.
  function OwnTabColumn({ [OWN_COLUMN]: { column, visible }, ...props }: OwnColumnProps) {
    useStore(placement);
    arrange(props.tabs, visible);
    return createElement(column, props);
  }

  // Runs after Decky's patch, which has already filled Steam's list for this render.
  const findMenu = (tree: unknown): unknown =>
    findInReactTree(tree, (node: unknown) => propsOf(node)?.onFocusNavDeactivated !== undefined);
  const wrapColumn = createReactTreePatcher(
    [findMenu],
    (args: unknown[], tree: unknown) => {
      const node: unknown = findInReactTree(tree, (candidate: unknown) => Array.isArray(propsOf(candidate)?.tabs));
      if (isElement(node) && node.type !== OwnTabColumn && isComponent(node.type)) {
        const stash: ColumnStash = { column: node.type, visible: propsOf(args[0])?.visible === true };
        node.props = { ...node.props, [OWN_COLUMN]: stash };
        node.type = OwnTabColumn;
      }
      return tree;
    },
    "ORIGAMI tab",
  );
  const patches: Patch[] = renderers.map((renderer) => afterPatch(renderer, "type", wrapColumn));
  refreshMountedMenu(renderers);

  return {
    apply(enabled, position) {
      if (enabled && !registered()) hook.add({ id: ORIGAMI_TAB, ...tab });
      else if (!enabled && registered()) hook.removeById(ORIGAMI_TAB);
      const current = placement.get();
      if (current.enabled !== enabled || current.position !== position) placement.set({ enabled, position });
    },
    shown: registered,
    dispose() {
      for (const patch of patches) patch.unpatch();
      refreshMountedMenu(renderers);
      if (!registered()) return;
      hook.removeById(ORIGAMI_TAB);
      // Decky's own render never takes a tab out of a list it has filled; a plugin that replaced
      // the render takes ORIGAMI's entry out itself on the next render.
      if (!deckyRendersTabs(hook)) return;
      for (const tabs of columns) {
        const index = tabs.findIndex(isOwnTab);
        if (index >= 0) tabs.splice(index, 1);
      }
    },
  };
}
