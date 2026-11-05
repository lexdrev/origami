// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import { UISound } from "../sounds";
import { slide } from "./slider";

const tdp = { min: 7, max: 35, wrap: false };
const hue = { min: 0, max: 359, wrap: true };

describe("a slider step", () => {
  it("clicks up or down as Steam's sliders do", () => {
    expect(slide(tdp, 17, 18, 1)).toEqual({ value: 18, sound: UISound.SliderUp });
    expect(slide(tdp, 17, 16, -1)).toEqual({ value: 16, sound: UISound.SliderDown });
  });

  it("stays silent at an end, where the value does not move", () => {
    expect(slide(tdp, 35, 36, 1)).toEqual({ value: 35, sound: null });
    expect(slide(tdp, 7, 6, -1)).toEqual({ value: 7, sound: null });
  });

  it("stops at the end it overshoots", () => {
    expect(slide(tdp, 33, 40, 1)).toEqual({ value: 35, sound: UISound.SliderUp });
  });

  it("goes round a wrapping scale and still clicks the way it went", () => {
    expect(slide(hue, 359, 360, 1)).toEqual({ value: 0, sound: UISound.SliderUp });
    expect(slide(hue, 0, -1, -1)).toEqual({ value: 359, sound: UISound.SliderDown });
  });
});
