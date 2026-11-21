// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import {
  curveHere,
  curveName,
  curveSteps,
  DEFAULT_FAN_CURVE,
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

    // Cooled from 60 °C, the fans still turn as the point at 60 °C asks.
    expect(speedNow(curve, 59, 5200)).toBe(40);
    expect(speedNow(curve, 59, 4500)).toBe(25);
    expect(speedNow(curve, 37.4, 3800)).toBe(10);
    expect(speedNow(curve, 37.4, 0)).toBe(0);
    // Fans still gathering speed after a step are on the step asked, and never two steps above.
    expect(speedNow(curve, 63, 4800)).toBe(40);
    expect(speedNow(curve, 52, 6100)).toBe(40);
    expect(speedNow(curve, 95, 8000)).toBe(100);
    expect(speedNow(curve, 20, 3800)).toBe(0);
    expect(speedNow(curve, 59, null)).toBe(25);
    // The curve that holds a temperature: its level, or the step over the target it has not let go.
    expect(speedNow(held, 60, 5200)).toBe(40);
    expect(speedNow(held, 64.5, 5700)).toBe(50);
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

    expect(holdState(held, 60, 60.4)).toBe("holding");
    expect(holdState(full, 60, 65.1)).toBe("full");
    // At full speed for a moment only: the chip is at the target.
    expect(holdState(full, 60, 60.8)).toBe("holding");
    expect(holdState(slowest, 60, 54)).toBe("slowest");
    // A level still on its way down runs the fans; the chip being cooler is not yet their slowest.
    expect(holdState(held, 60, 55)).toBe("holding");
  });
});
