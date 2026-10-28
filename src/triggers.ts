// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import type { Conflicts, TriggerLevel, TriggerRumble, Triggers } from "./backend";

// Rumble of the impulse triggers (origami.triggers): in a game each chosen trigger follows the grip
// on its side. The motors answer in a narrow band, so there are three levels, not a fine scale, and
// the lighter feel is a pattern: taps, one short tap on each shot.

export const TRIGGER_CHOICES: readonly Triggers[] = ["right", "both"];

export type TriggerPattern = "steady" | "taps";

export const TRIGGER_PATTERNS: readonly TriggerPattern[] = ["steady", "taps"];

/** Strength of a trigger at a game's full rumble for each level, as origami.triggers.LEVEL_STRENGTH. */
export const TRIGGER_LEVELS = [
  { id: "soft", value: 20 },
  { id: "medium", value: 60 },
  { id: "strong", value: 100 },
] as const satisfies readonly { id: TriggerLevel; value: number }[];

/** Still triggers, as the system leaves them; switched on, the right one rumbles steadily at the middle level. */
export const STOCK_TRIGGER_RUMBLE: TriggerRumble = { enabled: false, triggers: "right", level: "medium", taps: false };

export function currentTriggerRumble(setting: TriggerRumble | null): TriggerRumble {
  return setting ?? STOCK_TRIGGER_RUMBLE;
}

/**
 * The plugin that keeps ORIGAMI off the triggers, when the screen should say so in its own block.
 * A plugin that owns the handle vibration too is named once, in the vibration's block.
 */
export function separateTriggerOwner({ vibration, triggers }: Conflicts): string | null {
  return triggers !== null && triggers !== vibration ? triggers : null;
}
