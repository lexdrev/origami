// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { UISound } from "../sounds";

export interface SliderScale {
  min: number;
  max: number;
  /** Past one end the value comes in at the other, as the hue goes round. */
  wrap: boolean;
}

export interface SliderMove {
  value: number;
  /** Steam's click of its own sliders, up or down; none when the value stays, at an end. */
  sound: UISound | null;
}

/**
 * Where a step or a tap takes the slider, and the click it makes. The way it went counts, not the
 * values: on a wrapping scale a step up past the top lands at the bottom and still clicks up.
 */
export function slide(scale: SliderScale, from: number, to: number, direction: -1 | 1): SliderMove {
  const { min, max, wrap } = scale;
  const span = max - min + 1;
  const value = wrap ? min + ((((to - min) % span) + span) % span) : Math.min(max, Math.max(min, to));
  if (value === from) return { value, sound: null };
  return { value, sound: direction > 0 ? UISound.SliderUp : UISound.SliderDown };
}
