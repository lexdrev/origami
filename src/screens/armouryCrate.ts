// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import type { ButtonAction } from "../backend";
import type { ActionText, Messages } from "../i18n";

/** Actions for a short press. Nothing reaches Steam from it, so "none" leaves the button dead. */
export const PRESS_ACTIONS: readonly ButtonAction[] = [
  "origami",
  "quick_access",
  "performance",
  "overlay",
  "lighting",
  "screenshot",
  "keyboard",
  "magnifier",
  "none",
];

/**
 * Actions for holding the button. Steam gets L5 from it in any case; "none" leaves only that.
 * Closing the game is here only: it waits for the button to be held a second time.
 */
export const HOLD_ACTIONS: readonly ButtonAction[] = [
  "none",
  "origami",
  "quick_access",
  "performance",
  "overlay",
  "lighting",
  "screenshot",
  "keyboard",
  "magnifier",
  "close_game",
];

export function pressText(action: ButtonAction, t: Messages): ActionText {
  return action === "none" ? t.armouryCrate.nothing : t.armouryCrate.actions[action];
}

export function holdText(action: ButtonAction, t: Messages): ActionText {
  return action === "none" ? t.armouryCrate.l5 : t.armouryCrate.actions[action];
}

/** The line under the button on the Gamepad screen; null while nothing is assigned, which is a problem. */
export function armouryCrateSummary(press: ButtonAction, hold: ButtonAction, t: Messages): string | null {
  if (press === "none" && hold === "none") return null;
  return t.armouryCrate.summary(pressText(press, t).name, holdText(hold, t).name);
}
