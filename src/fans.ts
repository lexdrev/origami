// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import type { FanCurve } from "./backend";
import type { Messages } from "./i18n";

// ORIGAMI's fan curve (origami.fans): seven points from 30 to 90 °C for both fans, and full speed
// at 100 °C that the user never sets. The firmware takes no curve that falls, and from 80 °C the
// fans run at least at half speed (BUGS.md, B07).

export const FAN_TEMPS = [30, 40, 50, 60, 70, 80, 90] as const;
export const FAN_STEP = 5;
const SAFE_FROM = 80;
const SAFE_PERCENT = 50;
const FULL_SPEED = 100;
const TOP_TEMP = 100;

export const FAN_PRESETS = [
  { id: "quiet", points: [0, 0, 15, 25, 40, 60, 90] },
  { id: "balance", points: [0, 10, 25, 40, 55, 75, 100] },
  { id: "power", points: [20, 30, 45, 60, 75, 90, 100] },
] as const;

export type FanPreset = (typeof FAN_PRESETS)[number];

/** The backend's FanCurve(): switched on the first time, the fans start on the balanced curve. */
export const DEFAULT_FAN_CURVE: FanCurve = { enabled: true, points: [...FAN_PRESETS[1].points] };

export function presetOf(points: readonly number[]): FanPreset | undefined {
  return FAN_PRESETS.find((preset) => preset.points.every((point, index) => point === points[index]));
}

/** The curve's name in the card's head and on the tile: off, the firmware's own. */
export function curveName(curve: FanCurve | null, t: Messages): string {
  if (!curve?.enabled) return t.fans.presets.default;
  return t.fans.presets[presetOf(curve.points)?.id ?? "custom"];
}

/** The points with one moved as far as the curve allows: between its neighbours, and not under half from 80 °C. */
export function movePoint(points: readonly number[], index: number, value: number): number[] {
  const low = Math.max(points[index - 1] ?? 0, (FAN_TEMPS[index] ?? 0) >= SAFE_FROM ? SAFE_PERCENT : 0);
  const high = points[index + 1] ?? FULL_SPEED;
  return points.map((point, at) => (at === index ? Math.min(high, Math.max(low, value)) : point));
}

/** The speed the curve asks at a temperature, between its points as the firmware goes. */
export function speedAt(points: readonly number[], temp: number): number {
  const curve = [...FAN_TEMPS.map((at, index) => [at, points[index] ?? 0] as const), [TOP_TEMP, FULL_SPEED] as const];
  let previous: readonly [number, number] | null = null;
  for (const [at, speed] of curve) {
    if (temp <= at) {
      if (previous === null) return speed;
      const [from, fromSpeed] = previous;
      return Math.round(fromSpeed + ((speed - fromSpeed) * (temp - from)) / (at - from));
    }
    previous = [at, speed];
  }
  return FULL_SPEED;
}
