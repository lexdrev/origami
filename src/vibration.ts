// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import type { Telemetry, Vibration } from "./backend";

// Strength of the handle vibration (origami.vibration), 0–100% for each handle. The controller
// comes at 100% and goes back to it after every sleep without ORIGAMI.

export const MAX_VIBRATION = 100;
export const VIBRATION_STEP = 5;
/** ORIGAMI's strength from the first start (DEFAULT_STRENGTH in the backend), switched on where it was never set. */
export const DEFAULT_VIBRATION: Vibration = { enabled: true, left: 50, right: 50 };

/** The middle of the scale, marked on the track as the saturation's default is. */
export const VIBRATION_NOTCH = MAX_VIBRATION / 2;

/** Strengths for both handles, as the saturation presets; a custom cell after them shows the rest. */
export const VIBRATION_PRESETS = [
  { id: "weak", value: 25 },
  { id: "medium", value: 50 },
  { id: "strong", value: 75 },
  { id: "max", value: 100 },
] as const;

export type VibrationPreset = (typeof VIBRATION_PRESETS)[number];

/**
 * The strength the handles have: ORIGAMI's, or until there is one what the driver last took;
 * null while neither is known.
 */
export function currentVibration(setting: Vibration | null, telemetry: Telemetry | null): Vibration | null {
  if (setting !== null) return setting;
  const driver = telemetry?.gamepad.vibrationPct;
  return driver ? { enabled: true, left: driver[0], right: driver[1] } : null;
}

/** "50%", "40 / 60%" when the handles differ, or the word for off. */
export function formatVibration({ enabled, left, right }: Vibration, off: string): string {
  if (!enabled) return off;
  return left === right ? `${left}%` : `${left} / ${right}%`;
}

export function presetOf({ left, right }: Vibration): VibrationPreset | undefined {
  return left === right ? VIBRATION_PRESETS.find((preset) => preset.value === left) : undefined;
}

/** The custom cell after the presets: "+" while a preset holds, else the strength off them. */
export function customDetail({ left, right }: Vibration, preset: VibrationPreset | undefined): string {
  if (preset !== undefined) return "+";
  return left === right ? `${left}%` : `${left}/${right}`;
}

/** Switched off or at zero on both handles: a test would have nothing to show. */
export function silent({ enabled, left, right }: Vibration): boolean {
  return !enabled || (left === 0 && right === 0);
}

/** One strength for both handles: the middle of the two, on the slider's step. */
export function together(vibration: Vibration): Vibration {
  const strength = Math.round((vibration.left + vibration.right) / 2 / VIBRATION_STEP) * VIBRATION_STEP;
  return { ...vibration, left: strength, right: strength };
}
