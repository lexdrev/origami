// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import type { Telemetry, Vibration } from "./backend";

// Strength of the handle vibration (origami.vibration), 0–100% for each handle. The controller
// comes at 100%, too strong for most, and goes back to it after every sleep without ORIGAMI.

export const MAX_VIBRATION = 100;
export const VIBRATION_STEP = 5;
export const FACTORY_VIBRATION: Vibration = { left: MAX_VIBRATION, right: MAX_VIBRATION };

export const VIBRATION_PRESETS = [
  { id: "off", value: 0 },
  { id: "weak", value: 25 },
  { id: "medium", value: 50 },
  { id: "strong", value: 75 },
] as const;

export type VibrationPreset = (typeof VIBRATION_PRESETS)[number];

/**
 * The strength the handles have: ORIGAMI's, or until there is one what the driver last took;
 * null while neither is known.
 */
export function currentVibration(setting: Vibration | null, telemetry: Telemetry | null): Vibration | null {
  if (setting !== null) return setting;
  const driver = telemetry?.gamepad.vibrationPct;
  return driver ? { left: driver[0], right: driver[1] } : null;
}

/** "50%", or "40 / 60%" when the handles differ. */
export function formatVibration({ left, right }: Vibration): string {
  return left === right ? `${left}%` : `${left} / ${right}%`;
}

export function presetOf({ left, right }: Vibration): VibrationPreset | undefined {
  return left === right ? VIBRATION_PRESETS.find((preset) => preset.value === left) : undefined;
}

/** Full strength drowns out what a game means by its rumble; the screen suggests half. */
export function tooStrong({ left, right }: Vibration): boolean {
  return Math.max(left, right) === MAX_VIBRATION;
}

/** One strength for both handles: the middle of the two, on the slider's step. */
export function together({ left, right }: Vibration): Vibration {
  const strength = Math.round((left + right) / 2 / VIBRATION_STEP) * VIBRATION_STEP;
  return { left: strength, right: strength };
}
