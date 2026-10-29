// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import { measure } from "./scrollbar";

/** A panel clientHeight px high, scrolled by scrollTop, with ORIGAMI's screen length px long in it. */
function panel(scrollTop: number, length: number, clientHeight: number): [HTMLElement, HTMLElement] {
  const rect = { top: 40, right: 340, height: clientHeight };
  const box = { scrollTop, clientHeight, getBoundingClientRect: () => rect } as unknown as HTMLElement;
  const bottom = rect.top + length - scrollTop;
  const content = { getBoundingClientRect: () => ({ bottom }) } as unknown as HTMLElement;
  return [box, content];
}

describe("panel scrollbar", () => {
  it("is not there while all of the screen is in view", () => {
    expect(measure(...panel(0, 446, 446))).toBeNull();
    // Decky's tab: the main screen ends at 439 px, and the panel scrolls 43 px of empty space past it.
    expect(measure(...panel(0, 439, 446))).toBeNull();
  });

  it("has a thumb as long as the part in view, where that part is", () => {
    // 446 of 679 px in view; the track is the box less 4 px at each end.
    expect(measure(...panel(0, 679, 446))).toEqual({ top: 44, left: 333, height: 438, thumbTop: 0, thumbHeight: 288 });
    expect(measure(...panel(233, 679, 446))?.thumbTop).toBe(150);
  });

  it("stays at the bottom while the panel is dragged past the screen's end", () => {
    expect(measure(...panel(276, 679, 446))?.thumbTop).toBe(150);
  });

  it("keeps a thumb that can be seen on a long screen", () => {
    expect(measure(...panel(0, 10000, 446))?.thumbHeight).toBe(24);
  });
});
