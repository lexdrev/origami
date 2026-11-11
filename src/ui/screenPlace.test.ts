// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import { openerAt } from "./screenPlace";

describe("the element a screen was left from", () => {
  it("is found at its place while the screen has as many focusable elements", () => {
    // The main screen: the screen, the gear, the grid and five tiles; the third tile opened.
    expect(openerAt(8, { index: 5, count: 8 })).toBe(5);
    expect(openerAt(8, { index: 0, count: 8 })).toBe(0);
  });

  it("is not looked for in another layout or when nothing had the focus", () => {
    expect(openerAt(9, { index: 5, count: 8 })).toBeNull();
    expect(openerAt(3, { index: 5, count: 3 })).toBeNull();
    expect(openerAt(8, undefined)).toBeNull();
  });
});
