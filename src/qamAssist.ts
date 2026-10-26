// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { addEventListener, removeEventListener } from "@decky/api";
import { Router } from "@decky/ui";

// While a game runs, Steam misses up to half of the quick access presses: the button sends a
// 16–20 ms pulse, and a press Steam misses leaves no trace in it (BUGS.md, B16). The backend
// reports every press; if Steam has not registered it shortly after, ORIGAMI does what Steam
// would have done, through the same menu store of the main window. A press Steam registered is
// left alone, so the menu never opens twice.

/** Sent by the backend (origami.app.QAM_PRESSED) on every press while QAM assist is on. */
const QAM_PRESSED = "qam_pressed";

/** Steam registers a press it sees 60–110 ms after it (check 14); ORIGAMI looks after that. */
export const STEAM_REACTION_MS = 250;

/** A press Steam registered this shortly before the backend's report is the same press. */
export const EARLY_PRESS_MS = 150;

// Steam's ESideMenu; @decky/ui has it only as a type.
const SideMenu = { None: 0, QuickAccess: 2 } as const;

export interface SteamMenuState {
  /** When Steam last registered a press of the button, on the performance.now() clock. */
  lastPressMs: number;
  openSideMenu: number;
}

export type Rescue = "open" | "close" | null;

/**
 * What to do about a press reported at `reportedAt`, from Steam's state then (`before`) and
 * STEAM_REACTION_MS later (`after`).
 */
export function rescueFor(before: SteamMenuState, after: SteamMenuState, reportedAt: number): Rescue {
  const steamSawIt =
    after.lastPressMs !== before.lastPressMs ||
    after.openSideMenu !== before.openSideMenu ||
    before.lastPressMs > reportedAt - EARLY_PRESS_MS;
  if (steamSawIt) return null;
  if (after.openSideMenu === SideMenu.None) return "open";
  if (after.openSideMenu === SideMenu.QuickAccess) return "close";
  return null;
}

const mainWindow = () => Router.WindowStore.GamepadUIMainWindowInstance;

function readSteamMenuState(): SteamMenuState | null {
  const window = mainWindow();
  // The press time is a field of Steam's main window that @decky/ui does not describe.
  if (!("m_flLastQuickAccessPressMS" in window)) return null;
  const lastPressMs = window.m_flLastQuickAccessPressMS;
  if (typeof lastPressMs !== "number") return null;
  return { lastPressMs, openSideMenu: window.MenuStore.GetOpenSideMenu() };
}

/** Starts making up for presses Steam misses; returns the function that stops it. */
export function watchQuickAccessButton(): () => void {
  const pending = new Set<ReturnType<typeof setTimeout>>();

  const onPress = () => {
    const reportedAt = performance.now();
    const before = readSteamMenuState();
    if (before === null) return;
    const check = setTimeout(() => {
      pending.delete(check);
      const after = readSteamMenuState();
      const rescue = after && rescueFor(before, after, reportedAt);
      const menus = mainWindow().MenuStore;
      // Steam's own press opens the menu on the tab it was left on. Without a tab,
      // OpenQuickAccessMenu would switch to the first one.
      if (rescue === "open") menus.OpenQuickAccessMenu(menus.GetQuickAccessTab());
      if (rescue === "close") menus.CloseSideMenus();
    }, STEAM_REACTION_MS);
    pending.add(check);
  };

  addEventListener(QAM_PRESSED, onPress);
  return () => {
    removeEventListener(QAM_PRESSED, onPress);
    for (const check of pending) clearTimeout(check);
  };
}
