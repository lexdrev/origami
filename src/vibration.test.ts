// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import type { Telemetry } from "./backend";
import { currentVibration, formatVibration, presetOf, together, tooStrong } from "./vibration";

describe("vibration", () => {
  const driver = (left: number, right: number) => ({ gamepad: { vibrationPct: [left, right] } }) as Telemetry;

  it("is ORIGAMI's once set, and the driver's until then", () => {
    expect(currentVibration({ left: 25, right: 25 }, driver(100, 100))).toEqual({ left: 25, right: 25 });
    expect(currentVibration(null, driver(64, 64))).toEqual({ left: 64, right: 64 });
    expect(currentVibration(null, null)).toBeNull();
  });

  it("shows one number when the handles agree", () => {
    expect(formatVibration({ left: 50, right: 50 })).toBe("50%");
    expect(formatVibration({ left: 40, right: 60 })).toBe("40 / 60%");
  });

  it("names the preset only for one strength on both handles", () => {
    expect(presetOf({ left: 0, right: 0 })?.id).toBe("off");
    expect(presetOf({ left: 75, right: 75 })?.id).toBe("strong");
    expect(presetOf({ left: 50, right: 75 })).toBeUndefined();
    expect(presetOf({ left: 60, right: 60 })).toBeUndefined();
  });

  it("calls full strength too strong", () => {
    expect(tooStrong({ left: 100, right: 100 })).toBe(true);
    expect(tooStrong({ left: 50, right: 100 })).toBe(true);
    expect(tooStrong({ left: 95, right: 95 })).toBe(false);
  });

  it("joins the handles in the middle, on the slider's step", () => {
    expect(together({ left: 40, right: 60 })).toEqual({ left: 50, right: 50 });
    expect(together({ left: 25, right: 30 })).toEqual({ left: 30, right: 30 });
  });
});
