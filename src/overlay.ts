// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { findModuleByExport } from "@decky/ui";

// Steam's performance overlay, the "Overlay level" of the Performance tab. Steam keeps the level in
// its performance settings store; the module of that store also holds the tab's hook, which reads
// msgSettingsGlobal.perf_overlay_level and sets it with SetPerfOverlayLevel (read from the Steam
// client on 2026-10-26). The level is Steam's EGraphicsPerfOverlayLevel, where Minimal came last.

/** The levels as the tab's slider shows them, off to the most detailed: Hidden, Minimal, Basic, Medium, Full. */
export const OVERLAY_LEVELS = [0, 4, 1, 2, 3] as const;

/** Steam takes a new level a moment after it is set; a press within this time goes on from it. */
const SETTLE_MS = 1000;

/** One level more detailed; after the most detailed one, off. */
export function nextOverlayLevel(level: number): number {
  const index = OVERLAY_LEVELS.findIndex((known) => known === level);
  return OVERLAY_LEVELS[(index + 1) % OVERLAY_LEVELS.length] ?? 0;
}

interface PerfSettingsStore {
  msgSettingsGlobal?: { perf_overlay_level?: number };
  SetPerfOverlayLevel: (level: number) => void;
}

function isPerfSettingsStore(value: unknown): value is PerfSettingsStore {
  return (
    typeof value === "object" &&
    value !== null &&
    "SetPerfOverlayLevel" in value &&
    typeof value.SetPerfOverlayLevel === "function"
  );
}

/** What a store class hands out from its static Get(), the singleton; null for any other export. */
function singletonOf(value: unknown): unknown {
  if (typeof value !== "function" || !("Get" in value) || typeof value.Get !== "function") return null;
  return (value.Get as () => unknown)();
}

let found: PerfSettingsStore | undefined;

function perfSettingsStore(): PerfSettingsStore | null {
  if (found !== undefined) return found;
  const module: unknown = findModuleByExport(
    (value: unknown) => typeof value === "function" && value.toString().includes("SetPerfOverlayLevel"),
  );
  if (typeof module !== "object" || module === null) return null;
  for (const value of Object.values(module)) {
    const store = singletonOf(value);
    if (isPerfSettingsStore(store)) {
      found = store;
      return store;
    }
  }
  return null;
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
