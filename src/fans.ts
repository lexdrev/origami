// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import type { FanCurve } from "./backend";
import type { Messages } from "./i18n";

// ORIGAMI's fan curve (origami.fans): seven points from 30 to 90 °C for both fans, and full speed
// at 100 °C that the user never sets. The firmware takes no curve that falls, and from 80 °C the
// fans run at least at half speed (BUGS.md, B07). The firmware draws no line between the points:
// the fans run at the speed of the last point the temperature has passed, and on the way down they
// keep that speed for some degrees under the point. Instead of the points the curve can hold a
// temperature: the backend then finds the speed for it and keeps it in the firmware, with steps to
// full speed over the target.

export const FAN_TEMPS = [30, 40, 50, 60, 70, 80, 90] as const;
export const FAN_STEP = 5;
const SAFE_FROM = 80;
const SAFE_PERCENT = 50;
const FULL_SPEED = 100;
const TOP_TEMP = 100;
/** The targets to choose from, in °C (origami.fans). */
export const HOLD_TARGETS = { min: 45, max: 75 } as const;

/** A point of the curve as the firmware takes it: °C and speed in percent. */
export type CurvePoint = readonly [number, number];

export const FAN_PRESETS = [
  { id: "quiet", points: [0, 0, 15, 25, 40, 60, 90] },
  { id: "balance", points: [0, 10, 25, 40, 55, 75, 100] },
  { id: "power", points: [20, 30, 45, 60, 75, 90, 100] },
] as const;

export type FanPreset = (typeof FAN_PRESETS)[number];

/** The backend's FanCurve(): switched on the first time, the fans start on the balanced curve. */
export const DEFAULT_FAN_CURVE: FanCurve = {
  enabled: true,
  points: [...FAN_PRESETS[1].points],
  hold: false,
  target: 60,
};

export function presetOf(points: readonly number[]): FanPreset | undefined {
  return FAN_PRESETS.find((preset) => preset.points.every((point, index) => point === points[index]));
}

/** The curve's name in the card's head and on the tile: off, the firmware's own. */
export function curveName(curve: FanCurve | null, t: Messages): string {
  if (!curve?.enabled) return t.fans.presets.default;
  return t.fans.presets[presetOf(curve.points)?.id ?? "custom"];
}

/** The curve as this console follows it: where the fans hold no temperature, by its points. */
export function curveHere(curve: FanCurve | null, canHold: boolean): FanCurve | null {
  return curve !== null && curve.hold && !canHold ? { ...curve, hold: false } : curve;
}

/** The temperature the fans hold, for the card's head and the tile; null while a curve runs them. */
export function heldTarget(curve: FanCurve | null): number | null {
  return curve !== null && curve.enabled && curve.hold ? curve.target : null;
}

/** The points with one moved as far as the curve allows: between its neighbours, and not under half from 80 °C. */
export function movePoint(points: readonly number[], index: number, value: number): number[] {
  const low = Math.max(points[index - 1] ?? 0, (FAN_TEMPS[index] ?? 0) >= SAFE_FROM ? SAFE_PERCENT : 0);
  const high = points[index + 1] ?? FULL_SPEED;
  return points.map((point, at) => (at === index ? Math.min(high, Math.max(low, value)) : point));
}

/** The user's points as the firmware takes them, with full speed at 100 °C. */
export function ownCurve(points: readonly number[]): CurvePoint[] {
  return [...FAN_TEMPS.map((at, index) => [at, points[index] ?? 0] as const), [TOP_TEMP, FULL_SPEED] as const];
}

/** The speed a curve asks at a temperature: that of the last point passed, as the firmware goes. */
export function speedOn(curve: readonly CurvePoint[], temp: number): number {
  let speed = curve[0]?.[1] ?? 0;
  for (const [at, asked] of curve) {
    if (at > temp) break;
    speed = asked;
  }
  return speed;
}

/**
 * How fast fan 1 turns at a speed asked, in percent and rpm, as measured on the ROG Xbox Ally X.
 * Other fans turn otherwise: only the consoles that hold a temperature tell a step by it.
 */
const RPM_AT: readonly CurvePoint[] = [
  [0, 0],
  [8, 3700],
  [15, 4000],
  [30, 4735],
  [45, 5460],
  [60, 6100],
  [70, 6600],
  [100, 8000],
];

function rpmAt(percent: number): number {
  const above = RPM_AT.findIndex(([asked]) => asked >= percent);
  const [high, fast] = RPM_AT[above] ?? [FULL_SPEED, 8000];
  const [low, slow] = RPM_AT[above - 1] ?? [high, fast];
  return high === low ? fast : slow + ((fast - slow) * (percent - low)) / (high - low);
}

/**
 * The speed the fans run at now, in percent. The firmware takes a step up at its point's temperature
 * and lets it go only some degrees under, so a chip that has cooled can still be on the step above
 * the one its temperature asks: the fans' own speed tells which of the two. Unknown, it is the step asked.
 */
export function speedNow(curve: readonly CurvePoint[], temp: number, rpm: number | null): number {
  const asked = speedOn(curve, temp);
  const above = curve.find(([at]) => at > temp)?.[1] ?? asked;
  if (rpm === null) return asked;
  return Math.abs(rpmAt(above) - rpm) < Math.abs(rpmAt(asked) - rpm) ? above : asked;
}

/** The curve as the fans follow it, for a chart: level from each point to the next, then the step. */
export function curveSteps(curve: readonly CurvePoint[]): CurvePoint[] {
  return curve.flatMap((point, index): CurvePoint[] => {
    const before = curve[index - 1];
    return before === undefined ? [point] : [[point[0], before[1]], point];
  });
}

export type HoldState = "holding" | "full" | "slowest";

/** A degree off the target counts as held: the backend rests within half of one. */
const HELD_WITHIN = 1;
/** The least a hold asks (origami.fans.HOLD_SLOWEST): asked for nothing, the fans would stop. */
const SLOWEST = 8;

/**
 * How the hold stands: the fans at full speed and the chip still warmer than asked, the fans at
 * their slowest and the chip cooler anyway, or the target held.
 */
export function holdState(curve: readonly CurvePoint[], target: number, temp: number): HoldState {
  const speed = speedOn(curve, temp);
  if (speed >= FULL_SPEED && temp > target + HELD_WITHIN) return "full";
  if (speed <= SLOWEST && temp < target - HELD_WITHIN) return "slowest";
  return "holding";
}
