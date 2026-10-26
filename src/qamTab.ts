// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import type { ReactNode } from "react";

/** Key of ORIGAMI's own tab in the quick access menu ("ORG" in ASCII). Steam's tabs use 0–7, Decky 999. */
export const ORIGAMI_TAB = 0x4f5247;
/** Steam's soundtracks tab (QuickAccessTab.Music); ORIGAMI's tab sits right above it by default. */
export const SOUNDTRACKS_TAB = 7;

/** Entry of Steam's quick access tab list. */
export interface SteamTab {
  key: number;
}

export interface TabContent {
  title: ReactNode;
  icon: ReactNode;
  content: ReactNode;
}

// Decky's own tabs hook (decky-loader frontend/src/tabs-hook.tsx, v3.3.0). It is internal to
// Decky, not part of @decky/api, so its shape is checked before use.
interface DeckyTabsHook {
  add: (tab: TabContent & { id: number }) => void;
  removeById: (id: number) => void;
  render: (this: DeckyTabsHook, existingTabs: SteamTab[], visible: boolean) => unknown;
}

declare global {
  interface Window {
    DeckyPluginLoader?: { tabsHook?: unknown };
  }
}

function isTabsHook(value: unknown): value is DeckyTabsHook {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return ["add", "removeById", "render"].every((name) => typeof candidate[name] === "function");
}

/** Moves the tab `key` right before the tab `before`, or to the end of the list when `before` is absent. */
export function placeTab(tabs: SteamTab[], key: number, before: number): void {
  const from = tabs.findIndex((tab) => tab.key === key);
  if (from < 0) return;
  const [moved] = tabs.splice(from, 1);
  if (moved === undefined) return;
  const anchor = tabs.findIndex((tab) => tab.key === before);
  tabs.splice(anchor < 0 ? tabs.length : anchor, 0, moved);
}

/**
 * Adds ORIGAMI's own tab to the quick access menu, right before the tab `before`.
 * Returns the function that removes it, or null when Decky's tabs hook is not available.
 */
export function installQamTab(tab: TabContent, before: number): (() => void) | null {
  const hook = window.DeckyPluginLoader?.tabsHook;
  if (!isTabsHook(hook)) {
    console.warn("ORIGAMI: Decky's tabs hook is not available; ORIGAMI stays inside the Decky tab");
    return null;
  }

  // Decky appends plugin tabs to the end of Steam's list on every render; the tab is moved
  // into place after that. The previous render may already be another plugin's wrapper
  // (Panel de Control has one), so it is called as is.
  const previous = hook.render;
  let steamTabs: SteamTab[] | null = null;
  let installed = true;
  const render: DeckyTabsHook["render"] = function (existingTabs, visible) {
    const result = previous.call(this, existingTabs, visible);
    if (installed) {
      steamTabs = existingTabs;
      placeTab(existingTabs, ORIGAMI_TAB, before);
    }
    return result;
  };
  hook.render = render;
  hook.add({ id: ORIGAMI_TAB, ...tab });

  return () => {
    installed = false;
    // If someone wrapped render after us, our wrapper stays in their chain as a pass-through.
    if (hook.render === render) hook.render = previous;
    hook.removeById(ORIGAMI_TAB);
    // Decky only ever appends to Steam's list, so the entry is taken out here.
    const index = steamTabs?.findIndex((entry) => entry.key === ORIGAMI_TAB) ?? -1;
    if (index >= 0) steamTabs?.splice(index, 1);
  };
}
