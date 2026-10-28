// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import { currentTriggerRumble, separateTriggerOwner, STOCK_TRIGGER_RUMBLE, TRIGGER_LEVELS } from "./triggers";

describe("trigger rumble", () => {
  it("keeps the triggers still until switched on, then starts with the right one steadily at the middle level", () => {
    expect(currentTriggerRumble(null)).toEqual({ enabled: false, triggers: "right", level: "medium", taps: false });
    const both = { enabled: true, triggers: "both", level: "strong", taps: true } as const;
    expect(currentTriggerRumble(both)).toEqual(both);
    expect(STOCK_TRIGGER_RUMBLE.enabled).toBe(false);
  });

  it("gives each level the backend's strength", () => {
    expect(TRIGGER_LEVELS.map((level) => level.value)).toEqual([20, 60, 100]);
  });

  it("names a plugin that owns the triggers once on the screen", () => {
    const none = { lighting: null, saturation: null, vibration: null, triggers: null, power: null, fans: null };
    expect(separateTriggerOwner(none)).toBeNull();
    // Ally Fix sets the vibration too: its block for the vibration speaks for the triggers.
    expect(separateTriggerOwner({ ...none, vibration: "Ally Fix", triggers: "Ally Fix" })).toBeNull();
    expect(separateTriggerOwner({ ...none, vibration: "Ally Vibe Control", triggers: "Ally Fix" })).toBe("Ally Fix");
  });
});
