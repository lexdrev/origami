// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import type { Lighting, LightMode, LightSpeed } from "./backend";

/** The backend's Lighting(): switching the lighting on for the first time starts a spiral. */
export const DEFAULT_LIGHTING: Lighting = {
  enabled: true,
  mode: "spiral",
  left: 0xffd200,
  right: 0xffd200,
  speed: "medium",
  brightness: 70,
};

// Saturated values: the LEDs wash out soft screen colours (red looked like wine, white bluish).
// White leans warm because the blue LEDs are the strongest.
export const PALETTE = [
  { id: "yellow", rgb: 0xffd200 },
  { id: "white", rgb: 0xffebd2 },
  { id: "red", rgb: 0xff0000 },
  { id: "pink", rgb: 0xff1a8c },
  { id: "violet", rgb: 0x8c00ff },
  { id: "blue", rgb: 0x0000ff },
  { id: "cyan", rgb: 0x00c8ff },
  { id: "green", rgb: 0x00ff00 },
] as const;

export type PaletteColour = (typeof PALETTE)[number];

export const LIGHT_MODES: readonly LightMode[] = ["static", "breathing", "rainbow", "spiral"];
export const LIGHT_SPEEDS: readonly LightSpeed[] = ["slow", "medium", "fast"];
/** Brightness in percent (origami.lighting): smooth for ORIGAMI's colours. */
export const BRIGHTNESS = { min: 5, max: 100, step: 5 } as const;

export type LightLevel = "low" | "medium" | "high";

/**
 * Rainbow and spiral bring their own colours, which only the controller's three levels dim: the
 * brightness up to each value takes that level, and choosing the level sets the value.
 */
export const LIGHT_LEVELS: readonly { id: LightLevel; brightness: number }[] = [
  { id: "low", brightness: 35 },
  { id: "medium", brightness: 70 },
  { id: "high", brightness: 100 },
];

/** Which of LIGHT_LEVELS rainbow and spiral show at the brightness. */
export function levelOf(brightness: number): number {
  const index = LIGHT_LEVELS.findIndex((level) => brightness <= level.brightness);
  return index < 0 ? LIGHT_LEVELS.length - 1 : index;
}

export const hex = (rgb: number) => `#${rgb.toString(16).padStart(6, "0").toUpperCase()}`;

/** Rainbow and spiral bring their own colours. */
export const usesColour = (mode: LightMode) => mode === "static" || mode === "breathing";

export const hasSpeed = (mode: LightMode) => mode !== "static";

/** Rainbow and spiral: brightness by the controller's levels, not by the colour. */
export const hasLevels = (mode: LightMode) => !usesColour(mode);

/** The palette colour both rings show, or null for anything else. */
export function paletteColour(lighting: Lighting): PaletteColour | null {
  if (lighting.left !== lighting.right) return null;
  return PALETTE.find((colour) => colour.rgb === lighting.left) ?? null;
}

export interface RingLook {
  background: string;
  boxShadow: string;
  animation: string;
  opacity: number;
}

const SPECTRUM_STOPS = "#ff3b3b, #ffb020, #f5e23d, #3ddc6a, #2ec5ff, #3b6bff, #b44bff, #ff3b3b";
const SPECTRUM = `conic-gradient(${SPECTRUM_STOPS})`;
/** Background of the "custom colour" swatch. */
export const SPECTRUM_SWATCH = `linear-gradient(135deg, ${SPECTRUM_STOPS})`;
const UNLIT = "#1f252d";
// One cycle of each effect from slow to fast, close to how fast the rings themselves go.
const CYCLES: Record<Exclude<LightMode, "static">, readonly [string, string, string]> = {
  breathing: ["4s", "2.4s", "1.3s"],
  rainbow: ["9s", "4.5s", "2s"],
  spiral: ["6s", "3s", "1.4s"],
};
const LEVEL_OPACITY = [0.45, 0.75, 1] as const;

const glow = (rgb: number, alpha: number) =>
  `0 0 13px rgba(${(rgb >> 16) & 255}, ${(rgb >> 8) & 255}, ${rgb & 255}, ${alpha})`;

/** How a ring looks on the screen; null lighting means ORIGAMI has not set any. */
export function ringLook(lighting: Lighting | null, rgb: number): RingLook {
  if (!lighting?.enabled) {
    return { background: UNLIT, boxShadow: "none", animation: "none", opacity: 1 };
  }
  const opacity = hasLevels(lighting.mode)
    ? (LEVEL_OPACITY[levelOf(lighting.brightness)] ?? 1)
    : 0.25 + (0.75 * lighting.brightness) / BRIGHTNESS.max;
  const cycle = lighting.mode === "static" ? "" : CYCLES[lighting.mode][LIGHT_SPEEDS.indexOf(lighting.speed)];
  switch (lighting.mode) {
    case "static":
      return { background: hex(rgb), boxShadow: glow(rgb, 0.55), animation: "none", opacity };
    case "breathing":
      return {
        background: hex(rgb),
        boxShadow: glow(rgb, 0.55),
        animation: `og-ring-breath ${cycle} ease-in-out infinite`,
        opacity,
      };
    case "rainbow":
      return {
        background: "#ff3b3b",
        boxShadow: glow(0xff3b3b, 0.55),
        animation: `og-ring-hue ${cycle} linear infinite`,
        opacity,
      };
    case "spiral":
      return {
        background: SPECTRUM,
        boxShadow: "0 0 12px rgba(255, 255, 255, 0.14)",
        animation: `og-ring-spin ${cycle} linear infinite`,
        opacity,
      };
  }
}

/** A colour as the custom colour screen edits it: hue 0–359°, saturation 0–100% (white to pure). */
export interface HueSaturation {
  hue: number;
  saturation: number;
}

/** The colour at full value: LEDs have no "darker", only brightness. */
export function hsToRgb({ hue, saturation }: HueSaturation): number {
  const chroma = saturation / 100;
  const x = chroma * (1 - Math.abs(((hue / 60) % 2) - 1));
  const white = 1 - chroma;
  const sector: readonly (readonly [number, number, number])[] = [
    [chroma, x, 0],
    [x, chroma, 0],
    [0, chroma, x],
    [0, x, chroma],
    [x, 0, chroma],
    [chroma, 0, x],
  ];
  const [red, green, blue] = sector[Math.floor(hue / 60) % 6] ?? [0, 0, 0];
  const byte = (channel: number) => Math.round((channel + white) * 255);
  return (byte(red) << 16) | (byte(green) << 8) | byte(blue);
}

export function rgbToHs(rgb: number): HueSaturation {
  const [red, green, blue] = [(rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255].map((channel) => channel / 255) as [
    number,
    number,
    number,
  ];
  const max = Math.max(red, green, blue);
  const chroma = max - Math.min(red, green, blue);
  let hue = 0;
  if (chroma > 0) {
    if (max === red) hue = ((green - blue) / chroma) % 6;
    else if (max === green) hue = (blue - red) / chroma + 2;
    else hue = (red - green) / chroma + 4;
  }
  return {
    hue: Math.round((hue * 60 + 360) % 360),
    saturation: max === 0 ? 0 : Math.round((chroma / max) * 100),
  };
}
