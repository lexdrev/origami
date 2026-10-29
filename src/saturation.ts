// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { backend } from "./backend";
import { updateSettings } from "./state";
import { createStore, latestOnly } from "./store";

// The screen saturation ORIGAMI writes to gamescope itself (origami.saturation):
// Steam's own Color Vibrance never reaches gamescope on this console. 0–200%, 100 being sRGB.

export const DEFAULT_SATURATION = 100;
export const MAX_SATURATION = 200;
export const SATURATION_STEP = 5;

export const SATURATION_PRESETS = [
  { id: "default", value: DEFAULT_SATURATION },
  { id: "brighter", value: 125 },
  { id: "vivid", value: 150 },
  { id: "max", value: MAX_SATURATION },
] as const;

export type SaturationPreset = (typeof SATURATION_PRESETS)[number];

/** What gamescope shows now, in percent; null where there is no gamescope to ask. */
export const saturation = createStore<number | null>(null);

export async function refreshSaturation(): Promise<void> {
  try {
    saturation.set(await backend.getSaturation());
  } catch (error) {
    console.warn("ORIGAMI: cannot read the saturation", error);
    saturation.set(null);
  }
}

// A slider moved quickly saves only its newest value; the screen then shows what gamescope took,
// unless a newer value waits: the slider would move back to one the user has left.
const save = latestOnly(async (value: number) => {
  await updateSettings({ saturation: value });
  if (!save.waiting()) await refreshSaturation();
});

export function setSaturation(percent: number): void {
  const value = Math.min(MAX_SATURATION, Math.max(0, Math.round(percent)));
  saturation.set(value);
  save.send(value);
}

export function presetOf(value: number): SaturationPreset | undefined {
  return SATURATION_PRESETS.find((preset) => preset.value === value);
}
