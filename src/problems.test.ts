// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import type { Conflicts, Settings } from "./backend";
import { buttonUnset, gyroProblem, tileProblems, type ProblemSources } from "./problems";

// A clean Bazzite with ORIGAMI just installed.
const fresh: Settings = {
  language: "auto",
  qamTab: true,
  qamTabBefore: 7,
  qamAssist: null,
  gyroFix: null,
  lighting: null,
  saturation: null,
  vibration: null,
  triggerRumble: null,
  armouryCrate: null,
  armouryCrateHold: null,
  manageTdp: true,
  power: { tdp: 17, headroom: true, cpuBoost: null },
  batteryHighTdp: false,
  gamePower: [],
  fans: null,
};

const alone: Conflicts = { lighting: null, saturation: null, vibration: null, triggers: null, power: null, fans: null };

const sources = (changes: Partial<ProblemSources> = {}): ProblemSources => ({
  settings: fresh,
  conflicts: alone,
  gyro: "wrong",
  triggers: "available",
  steamTdpSlider: false,
  contested: false,
  ...changes,
});

const clear = { power: 0, fans: 0, display: 0, gamepad: 0 };

describe("problems on the tiles", () => {
  it("are the four fixes on the Gamepad tile of a clean system", () => {
    expect(tileProblems(sources())).toEqual({ ...clear, gamepad: 4 });
  });

  it("leave what the user set, on or off", () => {
    const settings: Settings = {
      ...fresh,
      qamAssist: false,
      gyroFix: true,
      triggerRumble: { enabled: false, triggers: "right", level: "medium", taps: false },
      armouryCrate: "none",
    };

    expect(tileProblems(sources({ settings, gyro: "fixed" }))).toEqual(clear);
  });

  it("count only what the console has and what is known", () => {
    expect(tileProblems(sources({ triggers: "unavailable", gyro: "fixed_in_system" })).gamepad).toBe(2);
    expect(tileProblems(sources({ triggers: null, gyro: null })).gamepad).toBe(2);
  });

  it("count other plugins that own a feature, a plugin that owns both vibrations once", () => {
    const conflicts: Conflicts = {
      lighting: "HueSync",
      saturation: "vibrantDeck",
      vibration: "Ally Fix",
      triggers: "Ally Fix",
      power: "Panel de Control",
      fans: "Panel de Control",
    };

    expect(tileProblems(sources({ conflicts }))).toEqual({ power: 1, fans: 1, display: 2, gamepad: 4 });
    expect(tileProblems(sources({ conflicts: { ...alone, triggers: "Ally Fix" } })).gamepad).toBe(4);
  });

  it("count what fights ORIGAMI over the TDP while it keeps it", () => {
    expect(tileProblems(sources({ steamTdpSlider: true, contested: true })).power).toBe(2);
    const steamSets = { ...fresh, manageTdp: false };
    expect(tileProblems(sources({ settings: steamSets, steamTdpSlider: true, contested: true })).power).toBe(0);
  });

  it("count the TDP left to Steam by restoring until the user decides", () => {
    const restored = { ...fresh, manageTdp: null };
    expect(tileProblems(sources({ settings: restored, steamTdpSlider: true, contested: true })).power).toBe(1);
    // Another plugin owns the power, and its own block already says so.
    const owned = { ...alone, power: "Panel de Control" };
    expect(tileProblems(sources({ settings: restored, conflicts: owned })).power).toBe(1);
  });
});

describe("red fixes", () => {
  it("show another program's gyroscope axes, and the fix only until it is set", () => {
    expect(gyroProblem("foreign", true)).toBe(true);
    expect(gyroProblem("wrong", null)).toBe(true);
    expect(gyroProblem("wrong", false)).toBe(false);
    expect(gyroProblem("fixed_in_system", null)).toBe(false);
  });

  it("show the Armoury Crate button until either press is chosen", () => {
    expect(buttonUnset(null, null)).toBe(true);
    expect(buttonUnset("none", null)).toBe(false);
    expect(buttonUnset(null, "origami")).toBe(false);
  });
});
