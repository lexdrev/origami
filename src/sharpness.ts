// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import type { Sharpness, SharpnessGameState } from "./backend";

// Sharpening of the games' picture (origami.sharpness): contrast adaptive sharpening, loaded into
// a game as it starts. A game takes the setting once, so a change waits for its next start.

export const MAX_SHARPNESS = 100;
export const SHARPNESS_STEP = 5;

/** What the sharpness starts with the first time it is switched on (origami.sharpness.Sharpness). */
export const DEFAULT_SHARPNESS: Sharpness = { enabled: true, strength: 40 };
/** What the card shows, and a game's own sharpness starts from, until it is first switched on. */
export const UNSET_SHARPNESS: Sharpness = { ...DEFAULT_SHARPNESS, enabled: false };

export interface SharpnessPreset {
  id: "soft" | "medium" | "strong";
  value: number;
}

/** Medium is the sharpening layer's own default. */
export const SHARPNESS_PRESETS: readonly SharpnessPreset[] = [
  { id: "soft", value: 20 },
  { id: "medium", value: DEFAULT_SHARPNESS.strength },
  { id: "strong", value: 70 },
];

export function sharpnessPresetOf(strength: number): SharpnessPreset | undefined {
  return SHARPNESS_PRESETS.find((preset) => preset.value === strength);
}

/** What the card says under its title. */
export type SharpnessStatus =
  | "off"
  | "ready"
  | "working"
  | "turning_on"
  | "turning_off"
  | "new_strength"
  | "missing";

/**
 * The notice of a game whose sharpness is not ORIGAMI's (notices.ts), one for each plugin that
 * runs such games and one for the launch options that set the layer themselves: read once, it is
 * known for every game started the same way.
 */
export function takenNotice(owner: string | null): string {
  return `sharpness:${owner ?? "launch options"}`;
}

/**
 * How the sharpness stands: by the running game while this sharpness is the one it uses (`state`),
 * else by the switch alone. Null until the state is read, and for a sharpness no running game uses.
 */
export function sharpnessStatus(sharpness: Sharpness, state: SharpnessGameState | null): SharpnessStatus {
  // Switched off since the game started, the game still has the layer.
  if (state === "turning_off") return state;
  if (!sharpness.enabled) return "off";
  // A game whose sharpness is another plugin's shows no card at all.
  return state === null || state === "no_game" || state === "off" || state === "managed" ? "ready" : state;
}
