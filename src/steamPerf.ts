// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { findModuleByExport } from "@decky/ui";

// Steam's performance settings store, behind its Performance tab: the module that holds it also
// holds the tab's hook. The store hands out the global settings, the overlay level among them
// (read from the Steam client on 2026-10-26).

export interface PerfSettingsStore {
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

/** Steam's performance settings store; null when this Steam has none ORIGAMI knows. */
export function perfSettingsStore(): PerfSettingsStore | null {
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

