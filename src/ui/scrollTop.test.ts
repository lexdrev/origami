// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import { middleScroll, scrollMargins, topMargin } from "./scrollTop";

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

// The same screen with the Sound tile as a third row 431 px down: the panel scrolls 152 px, and the
// tab's title row stays over its top 36 px.
describe("scroll with the row in focus in the middle", () => {
  const rows = [
    [111, 263],
    [271, 423],
    [431, 582],
  ] as const;

  it("leaves the first row at the top, the last at the end, and centres the middle one under the title", () => {
    expect(rows.map(([top, bottom]) => middleScroll(top, bottom, 446, 36, 152))).toEqual([0, 106, 152]);
  });

  it("centres in the whole panel when nothing covers its top", () => {
    expect(middleScroll(271, 423, 446, 0, 152)).toBe(124);
  });

  it("does not scroll a panel that shows it all", () => {
    expect(middleScroll(271, 423, 446, 36, 0)).toBe(0);
    expect(middleScroll(271, 423, 446, 36, -3)).toBe(0);
  });

  it("gives margins with which the row fills the panel between its paddings at that scroll", () => {
    const padding = { top: PADDING, bottom: PADDING };
    // The middle row at 106: 117 px above it and 81 below make 350 px, the panel less its paddings.
    expect(scrollMargins(271, 423, 106, 446, padding)).toEqual({ top: "117px", bottom: "81px" });
    expect(scrollMargins(111, 263, 0, 446, padding)).toEqual({ top: "63px", bottom: "135px" });
    // The last row ends inside the bottom padding.
    expect(scrollMargins(431, 582, 152, 446, padding)).toEqual({ top: "231px", bottom: "-32px" });
  });
});
