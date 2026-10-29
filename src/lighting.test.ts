// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import type { Lighting } from "./backend";
import { DEFAULT_LIGHTING, hasSpeed, hex, hsToRgb, paletteColour, rgbToHs, ringLook, usesColour } from "./lighting";

const lighting = (changes: Partial<Lighting>): Lighting => ({ ...DEFAULT_LIGHTING, ...changes });

describe("lighting on the screen", () => {
  it("writes colours as the backend's hex", () => {
    expect(hex(0xffb020)).toBe("#FFB020");
    expect(hex(0x00000f)).toBe("#00000F");
  });

  it("asks for a colour and a speed only where the mode uses them", () => {
    expect([usesColour("static"), usesColour("breathing"), usesColour("rainbow")]).toEqual([true, true, false]);
    expect([hasSpeed("static"), hasSpeed("spiral")]).toEqual([false, true]);
  });

  it("starts a medium spiral when the lighting is switched on for the first time", () => {
    expect(DEFAULT_LIGHTING).toMatchObject({ enabled: true, mode: "spiral", speed: "medium", brightness: "medium" });
  });

  it("names a palette colour only when both rings show it", () => {
    expect(paletteColour(lighting({ mode: "static" }))?.id).toBe("yellow");
    expect(paletteColour(lighting({ left: 0xff3b3b, right: 0x3b6bff }))).toBeNull();
    expect(paletteColour(lighting({ left: 0x123456, right: 0x123456 }))).toBeNull();
  });
});

describe("the rings", () => {
  it("stay unlit until ORIGAMI sets the lighting, and when it is off", () => {
    expect(ringLook(null, 0xffb020).background).toBe("#1f252d");
    expect(ringLook(lighting({ enabled: false }), 0xffb020).animation).toBe("none");
  });

  it("glow in their colour, dimmer at a lower brightness", () => {
    const look = ringLook(lighting({ mode: "static", brightness: "low" }), 0xff3b3b);

    expect(look.background).toBe("#FF3B3B");
    expect(look.boxShadow).toContain("rgba(255, 59, 59");
    const bright = ringLook(lighting({ mode: "static", brightness: "high" }), 0xff3b3b);
    expect(look.opacity).toBeLessThan(bright.opacity);
  });

  it("play the effect faster at a higher speed", () => {
    expect(ringLook(lighting({ mode: "breathing", speed: "slow" }), 0).animation).toBe(
      "og-ring-breath 4s ease-in-out infinite",
    );
    expect(ringLook(lighting({ mode: "spiral", speed: "fast" }), 0).animation).toBe("og-ring-spin 1.4s linear infinite");
  });
});

describe("custom colours", () => {
  it("go from hue and saturation to the LED colour and back", () => {
    expect(hex(hsToRgb({ hue: 0, saturation: 100 }))).toBe("#FF0000");
    expect(hex(hsToRgb({ hue: 120, saturation: 0 }))).toBe("#FFFFFF");
    expect(hex(hsToRgb({ hue: 165, saturation: 45 }))).toBe("#8CFFE2");
    expect(rgbToHs(0x8cffe2)).toEqual({ hue: 165, saturation: 45 });
  });

  it("start from the palette colour the rings show", () => {
    expect(rgbToHs(0xffb020)).toEqual({ hue: 39, saturation: 87 });
    expect(rgbToHs(0x000000)).toEqual({ hue: 0, saturation: 0 });
  });
});
