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
import type { ReactNode } from "react";

import { FIRST_TAB, quickAccessColumn, type TabPosition } from "./tabPosition";

/** Key of ORIGAMI's own tab in the quick access menu ("ORG" in ASCII). Steam's tabs use 0–7, Decky 999. */
export const ORIGAMI_TAB = 0x4f5247;

/** Entry of Steam's quick access tab list. */
interface SteamTab {
  key: number;
  title?: unknown;
}

export interface TabContent {
  title: ReactNode;
  icon: ReactNode;
  content: ReactNode;
}

export interface OwnTab {
  /** Shows or hides ORIGAMI's tab and moves it to `position`. */
  apply: (enabled: boolean, position: TabPosition) => void;
  dispose: () => void;
}

// Decky's tabs hook (decky-loader frontend/src/tabs-hook.tsx, v3.3.0) renders plugin tabs with
// its error boundary and the visibility state @decky/api reads. It is internal to Decky, so only
// its add/removeById are used, after a shape check; its render is left alone because other
// plugins (Panel de Control) wrap it and skip their own tab when someone else got there first.
interface DeckyTabsHook {
  add: (tab: TabContent & { id: number }) => void;
  removeById: (id: number) => void;
}

declare global {
  interface Window {
    DeckyPluginLoader?: { tabsHook?: unknown };
  }
}

function isTabsHook(value: unknown): value is DeckyTabsHook {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.add === "function" && typeof candidate.removeById === "function";
}

/** Moves the tab `key` to `position`; a position before a tab that is not there means the end. */
export function placeTab(tabs: SteamTab[], key: number, position: TabPosition): void {
  const from = tabs.findIndex((tab) => tab.key === key);
  if (from < 0) return;
  const [moved] = tabs.splice(from, 1);
  if (moved === undefined) return;
  const anchor = position === FIRST_TAB ? 0 : tabs.findIndex((tab) => tab.key === position);
  tabs.splice(anchor < 0 ? tabs.length : anchor, 0, moved);
}

function propsOf(node: unknown): Record<string, unknown> | undefined {
  if (typeof node !== "object" || node === null || !("props" in node)) return undefined;
  const props = node.props;
  return typeof props === "object" && props !== null ? (props as Record<string, unknown>) : undefined;
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

function publishColumn(tabs: SteamTab[]): void {
  const column = tabs
    .filter((tab) => tab.key !== ORIGAMI_TAB)
    .map((tab) => ({ key: tab.key, title: typeof tab.title === "string" ? tab.title : null }));
  const current = quickAccessColumn.get();
  const changed = column.length !== current.length || column.some((tab, i) => tab.key !== current[i]?.key);
  // The menu is rendering right now; the settings screen re-renders after it, not inside it.
  if (changed) {
    queueMicrotask(() => {
      quickAccessColumn.set(column);
    });
  }
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

  let added = false;
  let position: TabPosition = null;
  let steamTabs: SteamTab[] | null = null;

  const removeFromColumn = () => {
    const index = steamTabs?.findIndex((entry) => entry.key === ORIGAMI_TAB) ?? -1;
    // Decky only ever appends to Steam's list, so the entry is taken out here.
    if (index >= 0) steamTabs?.splice(index, 1);
  };

  // Decky appends plugin tabs to Steam's list while the menu renders. This patch runs after
  // Decky's (and after any plugin that reorders its own tab) and only moves ORIGAMI's tab.
  const placeOrigami = createReactTreePatcher(
    [
      (tree: unknown) => {
        const menu: unknown = findInReactTree(tree, (node: unknown) => propsOf(node)?.onFocusNavDeactivated !== undefined);
        return menu;
      },
    ],
    (_args, tree: unknown) => {
      const tabs = propsOf(findInReactTree(tree, (node: unknown) => Array.isArray(propsOf(node)?.tabs)))?.tabs;
      if (Array.isArray(tabs)) {
        steamTabs = tabs as SteamTab[];
        placeTab(steamTabs, ORIGAMI_TAB, position);
        publishColumn(steamTabs);
      }
      return tree;
    },
    "ORIGAMI tab",
  );
  const patches: Patch[] = renderers.map((renderer) => afterPatch(renderer, "type", placeOrigami));
  refreshMountedMenu(renderers);

  return {
    apply(enabled, next) {
      position = next;
      if (enabled && !added) {
        hook.add({ id: ORIGAMI_TAB, ...tab });
        added = true;
      } else if (!enabled && added) {
        hook.removeById(ORIGAMI_TAB);
        removeFromColumn();
        added = false;
      }
      if (added && steamTabs) placeTab(steamTabs, ORIGAMI_TAB, position);
    },
    dispose() {
      for (const patch of patches) patch.unpatch();
      refreshMountedMenu(renderers);
      if (added) {
        hook.removeById(ORIGAMI_TAB);
        removeFromColumn();
      }
    },
  };
}
