// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import { measure } from "./scrollbar";

function box(scrollTop: number, scrollHeight: number, clientHeight: number): HTMLElement {
  const rect = { top: 40, right: 340, height: clientHeight };
  return { scrollTop, scrollHeight, clientHeight, getBoundingClientRect: () => rect } as unknown as HTMLElement;
}

describe("panel scrollbar", () => {
  it("is not there while all of the screen is in view", () => {
    expect(measure(box(0, 446, 446))).toBeNull();
  });

  it("has a thumb as long as the part in view, where that part is", () => {
    // 446 of 679 px in view; the track is the box less 4 px at each end.
    expect(measure(box(0, 679, 446))).toEqual({ top: 44, left: 333, height: 438, thumbTop: 0, thumbHeight: 288 });
    expect(measure(box(233, 679, 446))?.thumbTop).toBe(150);
  });

  it("keeps a thumb that can be seen on a long screen", () => {
    expect(measure(box(0, 10000, 446))?.thumbHeight).toBe(24);
  });
});
