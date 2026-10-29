// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import { en } from "../i18n/en";
import { ru } from "../i18n/ru";
import { armouryCrateSummary } from "./armouryCrate";

describe("Armoury Crate button summary", () => {
  it("names both presses", () => {
    expect(armouryCrateSummary("origami", "none", ru)).toBe("Коротко: ORIGAMI · долго: L5 в Steam");
    expect(armouryCrateSummary("none", "quick_access", en)).toBe("Short: Nothing · long: Steam quick access");
  });

  it("is a problem while nothing is assigned", () => {
    expect(armouryCrateSummary("none", "none", ru)).toBeNull();
    expect(armouryCrateSummary("l5", "none", ru)).toBe("Коротко: L5 в Steam · долго: L5 в Steam");
  });
});
