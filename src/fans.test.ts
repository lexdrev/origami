// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import { curveName, DEFAULT_FAN_CURVE, movePoint, presetOf, speedAt } from "./fans";
import { ru } from "./i18n/ru";

const balance = [0, 10, 25, 40, 55, 75, 100];

describe("fan curve", () => {
  it("starts on the balanced preset and names what it runs", () => {
    expect(DEFAULT_FAN_CURVE.points).toEqual(balance);
    expect(presetOf(balance)?.id).toBe("balance");
    expect(curveName(DEFAULT_FAN_CURVE, ru)).toBe("Баланс");
    expect(curveName({ enabled: true, points: [0, 10, 25, 45, 55, 75, 100] }, ru)).toBe("Своя");
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

  it("asks the speed between the points as the firmware does", () => {
    expect(speedAt(balance, 20)).toBe(0);
    expect(speedAt(balance, 64)).toBe(46);
    expect(speedAt(balance, 90)).toBe(100);
    expect(speedAt([0, 0, 15, 25, 40, 60, 90], 95)).toBe(95);
    expect(speedAt(balance, 105)).toBe(100);
  });
});
