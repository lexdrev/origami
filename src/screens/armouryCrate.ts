// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import type { ButtonAction } from "../backend";
import type { ActionText, Messages } from "../i18n";

/** Actions for a short press. Nothing reaches Steam from it, so "none" leaves the button dead. */
export const PRESS_ACTIONS: readonly ButtonAction[] = [
  "origami",
  "l5",
  "magnifier",
  "screenshot",
  "lighting",
  "quick_access",
  "performance",
  "overlay",
  "keyboard",
  "none",
];

/**
 * Actions for holding the button, in the short press's order. Steam gets L5 from it in any case;
 * "none" leaves only that, so it stands where L5 does. Closing the game is here only: it waits for
 * the button to be held a second time.
 */
export const HOLD_ACTIONS: readonly ButtonAction[] = [
  "origami",
  "none",
  "magnifier",
  "screenshot",
  "lighting",
  "quick_access",
  "performance",
  "overlay",
  "keyboard",
  "close_game",
];

export function pressText(action: ButtonAction, t: Messages): ActionText {
  if (action === "l5") return t.armouryCrate.l5;
  return action === "none" ? t.armouryCrate.nothing : t.armouryCrate.actions[action];
}

/** The held button gives Steam L5 by itself, so "l5" is no choice there. */
export function holdText(action: ButtonAction, t: Messages): ActionText {
  return action === "none" || action === "l5" ? t.armouryCrate.l5 : t.armouryCrate.actions[action];
}

/** The line under the button on the Gamepad screen; null while nothing is assigned, which is a problem. */
export function armouryCrateSummary(press: ButtonAction, hold: ButtonAction, t: Messages): string | null {
  if (press === "none" && hold === "none") return null;
  return t.armouryCrate.summary(pressText(press, t).name, holdText(hold, t).name);
}
