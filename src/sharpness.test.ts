// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import { DEFAULT_SHARPNESS, UNSET_SHARPNESS, sharpnessPresetOf, sharpnessStatus } from "./sharpness";

describe("the sharpness", () => {
  it("names the preset a strength is", () => {
    expect(sharpnessPresetOf(20)?.id).toBe("soft");
    expect(sharpnessPresetOf(DEFAULT_SHARPNESS.strength)?.id).toBe("medium");
    expect(sharpnessPresetOf(70)?.id).toBe("strong");
    expect(sharpnessPresetOf(55)).toBeUndefined();
  });

  it("is told by its switch while no game uses it", () => {
    expect(sharpnessStatus(DEFAULT_SHARPNESS, null)).toBe("ready");
    expect(sharpnessStatus(DEFAULT_SHARPNESS, "no_game")).toBe("ready");
    expect(sharpnessStatus(UNSET_SHARPNESS, null)).toBe("off");
    expect(sharpnessStatus(UNSET_SHARPNESS, "off")).toBe("off");
  });

  it("is told by the running game that uses it", () => {
    expect(sharpnessStatus(DEFAULT_SHARPNESS, "working")).toBe("working");
    expect(sharpnessStatus(DEFAULT_SHARPNESS, "missing")).toBe("missing");
    // A change made while the game runs waits for its next start, and says which change.
    expect(sharpnessStatus(DEFAULT_SHARPNESS, "turning_on")).toBe("turning_on");
    expect(sharpnessStatus(DEFAULT_SHARPNESS, "new_strength")).toBe("new_strength");
    expect(sharpnessStatus(UNSET_SHARPNESS, "turning_off")).toBe("turning_off");
  });
});
