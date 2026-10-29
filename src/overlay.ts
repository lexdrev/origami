// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { perfSettingsStore } from "./steamPerf";

// Steam's performance overlay, the "Overlay level" of the Performance tab. Steam keeps the level in
// its performance settings store (steamPerf), which reads msgSettingsGlobal.perf_overlay_level and
// sets it with SetPerfOverlayLevel. The level is Steam's EGraphicsPerfOverlayLevel, where Minimal
// came last.

/** The levels as the tab's slider shows them, off to the most detailed: Hidden, Minimal, Basic, Medium, Full. */
export const OVERLAY_LEVELS = [0, 4, 1, 2, 3] as const;

/** Steam takes a new level a moment after it is set; a press within this time goes on from it. */
const SETTLE_MS = 1000;

/** One level more detailed; after the most detailed one, off. */
export function nextOverlayLevel(level: number): number {
  const index = OVERLAY_LEVELS.findIndex((known) => known === level);
  return OVERLAY_LEVELS[(index + 1) % OVERLAY_LEVELS.length] ?? 0;
}

let lastSet: { level: number; at: number } | null = null;

/** Shows the overlay one level more detailed; false when Steam's store is not there. */
export function cycleOverlay(): boolean {
  const store = perfSettingsStore();
  if (store === null) return false;
  const now = performance.now();
  const current =
    lastSet !== null && now - lastSet.at < SETTLE_MS ? lastSet.level : (store.msgSettingsGlobal?.perf_overlay_level ?? 0);
  const level = nextOverlayLevel(current);
  store.SetPerfOverlayLevel(level);
  lastSet = { level, at: now };
  return true;
}
