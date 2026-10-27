// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import type { Telemetry } from "./backend";
import { currentVibration, customDetail, formatVibration, presetOf, silent, together } from "./vibration";

describe("vibration", () => {
  const driver = (left: number, right: number) => ({ gamepad: { vibrationPct: [left, right] } }) as Telemetry;

  const on = (left: number, right: number) => ({ enabled: true, left, right });

  it("is ORIGAMI's once set, and the driver's until then", () => {
    expect(currentVibration(on(25, 25), driver(100, 100))).toEqual(on(25, 25));
    expect(currentVibration(null, driver(64, 64))).toEqual(on(64, 64));
    expect(currentVibration(null, null)).toBeNull();
  });

  it("shows one number when the handles agree, and the word for off", () => {
    expect(formatVibration(on(50, 50), "Off")).toBe("50%");
    expect(formatVibration(on(40, 60), "Off")).toBe("40 / 60%");
    expect(formatVibration({ enabled: false, left: 50, right: 50 }, "Off")).toBe("Off");
  });

  it("names the preset only for one strength on both handles", () => {
    expect(presetOf(on(75, 75))?.id).toBe("strong");
    expect(presetOf(on(100, 100))?.id).toBe("max");
    expect(presetOf(on(50, 75))).toBeUndefined();
    expect(presetOf(on(60, 60))).toBeUndefined();
  });

  it("shows in the custom cell what no preset holds", () => {
    expect(customDetail(on(75, 75), presetOf(on(75, 75)))).toBe("+");
    expect(customDetail(on(65, 65), undefined)).toBe("65%");
    expect(customDetail(on(40, 60), undefined)).toBe("40/60");
  });

  it("calls the handles silent when switched off or at zero on both", () => {
    expect(silent(on(0, 0))).toBe(true);
    expect(silent({ enabled: false, left: 50, right: 50 })).toBe(true);
    expect(silent(on(0, 5))).toBe(false);
  });

  it("joins the handles in the middle, on the slider's step", () => {
    expect(together(on(40, 60))).toEqual(on(50, 50));
    expect(together(on(25, 30))).toEqual(on(30, 30));
  });
});
