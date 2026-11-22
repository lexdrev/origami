// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import type { HoldFans } from "./backend";
import {
  curveHere,
  curveName,
  curveSteps,
  DEFAULT_FAN_CURVE,
  heldAt,
  heldTarget,
  holdState,
  movePoint,
  ownCurve,
  presetOf,
  speedNow,
  speedOn,
  type CurvePoint,
} from "./fans";
import { ru } from "./i18n/ru";

const balance = [0, 10, 25, 40, 55, 75, 100];
// The backend's curve for 60 °C at the level it starts from (origami.fans.hold_curve).
const held: CurvePoint[] = [
  [30, 40],
  [64, 40],
  [65, 50],
  [66, 65],
  [67, 80],
  [68, 90],
  [70, 100],
  [100, 100],
];

// The fans as the backend knows them (origami.fans): the Xbox Ally X's and the first ROG Ally's.
const XBOX_ALLY_X: HoldFans = {
  slowest: 8,
  rpm: [
    [0, 0],
    [8, 3700],
    [15, 4000],
    [30, 4735],
    [45, 5460],
    [60, 6100],
    [70, 6600],
    [100, 8000],
  ],
  floor: null,
};
const ROG_ALLY: HoldFans = {
  slowest: 15,
  rpm: [
    [0, 0],
    [10, 3300],
    [15, 3500],
    [25, 4100],
    [30, 4400],
    [45, 5200],
    [60, 6000],
    [75, 6800],
    [90, 7400],
    [100, 7700],
  ],
  floor: { at: 60, back: 56, percent: 50 },
};

describe("fan curve", () => {
  it("starts on the balanced preset and names what it runs", () => {
    expect(DEFAULT_FAN_CURVE.points).toEqual(balance);
    expect(presetOf(balance)?.id).toBe("balance");
    expect(curveName(DEFAULT_FAN_CURVE, ru)).toBe("Баланс");
    expect(curveName({ ...DEFAULT_FAN_CURVE, points: [0, 10, 25, 45, 55, 75, 100] }, ru)).toBe("Своя");
    // Off, the firmware runs its own curve.
    expect(curveName({ ...DEFAULT_FAN_CURVE, enabled: false }, ru)).toBe("Дефолт");
    expect(curveName(null, ru)).toBe("Дефолт");
  });

  it("moves a point only between its neighbours", () => {
    expect(movePoint(balance, 3, 45)).toEqual([0, 10, 25, 45, 55, 75, 100]);
    expect(movePoint(balance, 3, 60)).toEqual([0, 10, 25, 55, 55, 75, 100]);
    expect(movePoint(balance, 3, 5)).toEqual([0, 10, 25, 25, 55, 75, 100]);
  });

  it("keeps the fans at half speed or more from 80 °C", () => {
    expect(movePoint([0, 0, 10, 20, 30, 60, 90], 5, 35)).toEqual([0, 0, 10, 20, 30, 50, 90]);
  });

  it("asks the speed of the last point passed, as the firmware does", () => {
    const curve = ownCurve(balance);

    expect(speedOn(curve, 20)).toBe(0);
    expect(speedOn(curve, 59.9)).toBe(25);
    expect(speedOn(curve, 64)).toBe(40);
    expect(speedOn(curve, 90)).toBe(100);
    expect(speedOn(ownCurve([0, 0, 15, 25, 40, 60, 90]), 95)).toBe(90);
    expect(speedOn(curve, 105)).toBe(100);
    expect(ownCurve(balance)).toEqual([...[30, 40, 50, 60, 70, 80, 90].map((at, index) => [at, balance[index]]), [100, 100]]);
  });

  it("tells the step the fans still keep from the one the temperature asks", () => {
    const curve = ownCurve(balance);

    const now = (points: readonly CurvePoint[], temp: number, rpm: number | null) =>
      speedNow(points, temp, rpm, XBOX_ALLY_X);

    // Cooled from 60 °C, the fans still turn as the point at 60 °C asks.
    expect(now(curve, 59, 5200)).toEqual({ percent: 40, byFirmware: false });
    expect(now(curve, 59, 4500).percent).toBe(25);
    expect(now(curve, 37.4, 3800).percent).toBe(10);
    expect(now(curve, 37.4, 0).percent).toBe(0);
    // Fans still gathering speed after a step are on the step asked, and never two steps above.
    expect(now(curve, 63, 4800).percent).toBe(40);
    expect(now(curve, 52, 6100).percent).toBe(40);
    expect(now(curve, 95, 8000).percent).toBe(100);
    expect(now(curve, 20, 3800).percent).toBe(0);
    expect(now(curve, 59, null).percent).toBe(25);
    // Fans nothing is measured of: the step the temperature asks.
    expect(speedNow(curve, 59, 5200, null).percent).toBe(25);
    // The curve that holds a temperature: its level, or the step over the target it has not let go.
    expect(now(held, 60, 5200).percent).toBe(40);
    expect(now(held, 64.5, 5700).percent).toBe(50);
  });

  it("tells the firmware's floor from the curve by the fans' speed", () => {
    const flat = ownCurve([15, 15, 15, 15, 15, 50, 90]);
    const quiet = ownCurve([0, 0, 15, 25, 40, 60, 90]);
    const now = (points: readonly CurvePoint[], temp: number, rpm: number) => speedNow(points, temp, rpm, ROG_ALLY);

    // The ROG Ally's owner, 2026-11-22: 15% asked at 64 °C, and the fans at 5400 rpm.
    expect(now(flat, 64, 5400)).toEqual({ percent: 50, byFirmware: true });
    expect(now(quiet, 61, 5400)).toEqual({ percent: 50, byFirmware: true });
    // The floor holds until the chip is back at 56 °C, and not under it.
    expect(now(flat, 57, 5300)).toEqual({ percent: 50, byFirmware: true });
    expect(now(flat, 55, 5300)).toEqual({ percent: 15, byFirmware: false });
    // Under the floor's start the fans follow the curve.
    expect(now(flat, 58, 3500)).toEqual({ percent: 15, byFirmware: false });
    // A curve that asks more than the floor runs the fans itself.
    expect(now(ownCurve([20, 30, 45, 60, 75, 90, 100]), 64, 6000)).toEqual({ percent: 60, byFirmware: false });
  });

  it("follows the points where the fans hold no temperature", () => {
    const holding = { ...DEFAULT_FAN_CURVE, hold: true, target: 55 };

    expect(curveHere(holding, true)).toBe(holding);
    expect(curveHere(holding, false)).toEqual({ ...holding, hold: false });
    expect(curveHere(DEFAULT_FAN_CURVE, false)).toBe(DEFAULT_FAN_CURVE);
    expect(curveHere(null, false)).toBeNull();
  });

  it("holds a temperature only while it is on and asked to", () => {
    expect(heldTarget({ ...DEFAULT_FAN_CURVE, hold: true, target: 55 })).toBe(55);
    expect(heldTarget(DEFAULT_FAN_CURVE)).toBeNull();
    expect(heldTarget({ ...DEFAULT_FAN_CURVE, hold: true, enabled: false })).toBeNull();
    expect(heldTarget(null)).toBeNull();
  });

  it("reads the speed off the curve that holds a temperature", () => {
    expect(speedOn(held, 25)).toBe(40);
    expect(speedOn(held, 60)).toBe(40);
    expect(speedOn(held, 64.9)).toBe(40);
    expect(speedOn(held, 65)).toBe(50);
    expect(speedOn(held, 69)).toBe(90);
    expect(speedOn(held, 75)).toBe(100);
  });

  it("draws a curve as the steps the fans take", () => {
    expect(curveSteps(held.slice(0, 4))).toEqual([
      [30, 40],
      [64, 40],
      [64, 40],
      [65, 40],
      [65, 50],
      [66, 50],
      [66, 65],
    ]);
    expect(curveSteps([])).toEqual([]);
  });

  it("tells a target held from one the fans cannot reach either way", () => {
    const full: CurvePoint[] = held.map(([at]) => [at, 100]);
    const slowest: CurvePoint[] = held.map(([at, speed]) => [at, Math.max(8, speed - 32)]);

    expect(holdState(held, 60, 60.4, XBOX_ALLY_X, false)).toBe("holding");
    expect(holdState(full, 60, 65.1, XBOX_ALLY_X, false)).toBe("full");
    // At full speed for a moment only: the chip is at the target.
    expect(holdState(full, 60, 60.8, XBOX_ALLY_X, false)).toBe("holding");
    expect(holdState(slowest, 60, 54, XBOX_ALLY_X, false)).toBe("slowest");
    // A level still on its way down runs the fans; the chip being cooler is not yet their slowest.
    expect(holdState(held, 60, 55, XBOX_ALLY_X, false)).toBe("holding");
  });

  it("tells a hold kept under the firmware's floor, and one the floor keeps cooler than asked", () => {
    const at = (temp: number, level: number): CurvePoint[] => [
      [30, level],
      ...[35, 50, 65, 80, 90].map((least, step): CurvePoint => [temp + 4 + step, Math.max(level, least)]),
      [temp + 10, 100],
      [100, 100],
    ];

    // 65 °C asked, 58 °C held with slower fans than the floor's.
    expect(heldAt(at(58, 35), 65)).toBe(58);
    expect(holdState(at(58, 35), 65, 58.2, ROG_ALLY, false)).toBe("under");
    expect(holdState(at(58, 35), 58, 58.2, ROG_ALLY, false)).toBe("holding");
    // A light load: the fans at this console's slowest, whatever is held.
    expect(holdState(at(58, 15), 65, 50, ROG_ALLY, false)).toBe("slowest");
    // The chip at the floor: the target itself is held, and the floor's speed keeps it cooler.
    expect(holdState(at(65, 50), 65, 63, ROG_ALLY, false)).toBe("floor");
    expect(holdState(at(65, 55), 65, 65.2, ROG_ALLY, false)).toBe("holding");
    // The firmware still has the fans after a heavy scene, as their speed tells.
    expect(holdState(at(58, 30), 58, 56.5, ROG_ALLY, true)).toBe("floor");
    expect(heldAt([], 65)).toBe(65);
  });
});
