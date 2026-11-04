// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { backend } from "./backend";
import { updateSettings } from "./state";
import { createStore, latestOnly } from "./store";

// The screen saturation ORIGAMI writes to gamescope itself (origami.saturation). 100% is what the
// system shows by itself: on Bazzite gamescope's 0.5, so 0–200%; SteamOS sets the widest, 1.0,
// itself, so there 0–100% and ORIGAMI can only take some away.

export const DEFAULT_SATURATION = 100;
export const MAX_SATURATION = 200;
export const STEAMOS_MAX_SATURATION = 100;
export const SATURATION_STEP = 5;

export interface SaturationPreset {
  id: "default" | "brighter" | "vivid" | "max" | "accurate" | "soft" | "system";
  value: number;
}

export const SATURATION_PRESETS: readonly SaturationPreset[] = [
  { id: "default", value: DEFAULT_SATURATION },
  { id: "brighter", value: 125 },
  { id: "vivid", value: 150 },
  { id: "max", value: MAX_SATURATION },
];

/** On SteamOS: gamescope's own colours, halfway, and what SteamOS shows. */
export const STEAMOS_SATURATION_PRESETS: readonly SaturationPreset[] = [
  { id: "accurate", value: 0 },
  { id: "soft", value: 50 },
  { id: "system", value: STEAMOS_MAX_SATURATION },
];

export interface SaturationScale {
  max: number;
  presets: readonly SaturationPreset[];
  steamos: boolean;
}

/** The scale on a system, by the ID in its os-release. */
export function saturationScale(systemId: string | null): SaturationScale {
  return systemId === "steamos"
    ? { max: STEAMOS_MAX_SATURATION, presets: STEAMOS_SATURATION_PRESETS, steamos: true }
    : { max: MAX_SATURATION, presets: SATURATION_PRESETS, steamos: false };
}

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

export function setSaturation(percent: number, max: number = MAX_SATURATION): void {
  const value = Math.min(max, Math.max(0, Math.round(percent)));
  saturation.set(value);
  save.send(value);
}

export function presetOf(value: number, presets: readonly SaturationPreset[] = SATURATION_PRESETS) {
  return presets.find((preset) => preset.value === value);
}
