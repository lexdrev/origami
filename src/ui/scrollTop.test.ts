// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import { topMargin } from "./scrollTop";

// The main screen in ORIGAMI's tab on the console: the panel is 446 px high, 14 px from the window's
// top, with Steam's 48 px scroll padding; the tile rows start 111 and 271 px down, each 152 px high.
const PADDING = 48;

function box(scrollTop: number): HTMLElement {
  return { scrollTop, clientHeight: 446, getBoundingClientRect: () => ({ top: 14 }) } as unknown as HTMLElement;
}

/** A tile `top` px from the start of the panel's content. */
function tile(top: number, scrollTop: number, height = 152): HTMLElement {
  const rect = { top: 14 + top - scrollTop, height };
  return { getBoundingClientRect: () => rect } as unknown as HTMLElement;
}

describe("scroll to the panel's top", () => {
  it("gives the first row of tiles a margin up to the panel's top, however far it is scrolled", () => {
    expect(topMargin(tile(111, 63), box(63), PADDING)).toBe("111px");
    expect(topMargin(tile(111, 153), box(153), PADDING)).toBe("111px");
    expect(topMargin(tile(111, 0), box(0), PADDING)).toBe("111px");
  });

  it("leaves a row that reaches into the bottom padding to Steam", () => {
    expect(topMargin(tile(271, 0), box(0), PADDING)).toBe("");
    expect(topMargin(tile(431, 153), box(153), PADDING)).toBe("");
  });

  it("counts the element's whole height", () => {
    expect(topMargin(tile(246, 0), box(0), PADDING)).toBe("246px");
    expect(topMargin(tile(247, 0), box(0), PADDING)).toBe("");
    expect(topMargin(tile(247, 0), box(0), 0)).toBe("247px");
  });
});
