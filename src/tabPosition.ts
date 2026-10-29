// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import type { Messages } from "./i18n";
import { createStore } from "./store";

/** Position before every other tab (the backend's FIRST_TAB). */
export const FIRST_TAB = -1;

/** Where ORIGAMI's tab stands: before this Steam tab, FIRST_TAB on top, null at the end. */
export type TabPosition = number | null;

/** A tab of Steam's quick access column, ORIGAMI's own tab left out. */
export interface ColumnTab {
  key: number;
  /** Plain-text title; Steam's own tabs have localized elements there and are named by key. */
  title: string | null;
}

/** A plugin that arranges the column itself; ORIGAMI then leaves its tab where that plugin puts it. */
export interface Arranger {
  /** The plugin's name in Decky; null when ORIGAMI does not know the plugin. */
  name: string | null;
}

/** Steam's column as of the last time the quick access menu was drawn. */
export interface QuickAccessColumn {
  /** The tabs without ORIGAMI. */
  tabs: readonly ColumnTab[];
  /** Null while ORIGAMI places its tab itself. */
  arranger: Arranger | null;
}

export const quickAccessColumn = createStore<QuickAccessColumn>({ tabs: [], arranger: null });

/** Index ORIGAMI takes among the other tabs; a tab that is gone means the end. */
export function ownTabIndex(column: readonly ColumnTab[], position: TabPosition): number {
  if (position === FIRST_TAB) return 0;
  const index = column.findIndex((tab) => tab.key === position);
  return index < 0 ? column.length : index;
}

/**
 * Position to store for ORIGAMI at `index` among the other tabs. The top is FIRST_TAB rather
 * than "before tab X", so it stays on top when another plugin adds a tab there.
 */
export function positionAt(column: readonly ColumnTab[], index: number): TabPosition {
  if (index <= 0) return FIRST_TAB;
  return column[index]?.key ?? null;
}

// Steam's QuickAccessTab keys.
const STEAM_TABS: Record<number, keyof Messages["tabs"]> = {
  0: "notifications",
  1: "remotePlay",
  2: "voiceChat",
  3: "friends",
  4: "quickSettings",
  5: "performance",
  6: "help",
  7: "soundtracks",
  999: "decky",
};

export function tabName(tab: ColumnTab, t: Messages): string {
  const steamTab = STEAM_TABS[tab.key];
  return steamTab ? t.tabs[steamTab] : (tab.title ?? t.tabs.plugin);
}

/** Line under "Quick access tab" in the settings. */
export function ownTabSummary(
  enabled: boolean,
  position: TabPosition,
  column: QuickAccessColumn,
  t: Messages,
): string {
  if (!enabled) return t.settings.qamTabOff;
  if (column.arranger) return t.settings.qamTabArranged(column.arranger.name);
  const index = ownTabIndex(column.tabs, position);
  const next = column.tabs[index];
  if (index === 0) return t.settings.qamTabFirst;
  return next ? t.settings.qamTabAbove(tabName(next, t)) : t.settings.qamTabLast;
}
