// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import type { ButtonAction, ConsoleButton, Conflicts, GyroState, Settings, TriggerState } from "./backend";
import { separateTriggerOwner } from "./triggers";

// What the screens show red, and so what a tile on the main screen counts: a fix of a system bug the
// user has not set yet, something that fights ORIGAMI right now, and another plugin that owns a
// feature. A fix the user switched off is their choice and stays grey, as anything on by default.

/** Whether ORIGAMI may drive this button here; while not known yet, it is not counted. */
export function drives(buttons: readonly ConsoleButton[] | null, button: ConsoleButton): boolean {
  return buttons?.includes(button) === true;
}

/** A setting the user has never set; for a fix of a system bug, the bug is still there. */
export function unset(setting: unknown): boolean {
  return setting === null;
}

/** Another program's axes, or ORIGAMI's fix never set where the axes are wrong. */
export function gyroProblem(state: GyroState, fix: boolean | null): boolean {
  switch (state) {
    case "foreign":
      return true;
    case "wrong":
    case "fixed":
    case "outdated":
      return unset(fix);
    case "unavailable":
    case "fixed_in_system":
      return false;
  }
}

/** The Armoury Crate button does nothing, and nobody has chosen so. */
export function buttonUnset(press: ButtonAction | null, hold: ButtonAction | null): boolean {
  return unset(press) && unset(hold);
}

export interface ProblemSources {
  settings: Settings;
  conflicts: Conflicts;
  /** Null until read: what is not known yet is not counted. */
  gyro: GyroState | null;
  triggers: TriggerState | null;
  /** The buttons ORIGAMI may drive here; null until known, when neither button counts. */
  buttons: readonly ConsoleButton[] | null;
  /** Steam's TDP slider is on while ORIGAMI keeps the TDP. */
  steamTdpSlider: boolean;
  /** Something else keeps writing the TDP. */
  contested: boolean;
  /** The crackle after sleep happens here; null until read. */
  clockCrackle: boolean | null;
  /** The system has an overlay menu ORIGAMI can keep in sight; null until known. */
  overlayMenu: boolean | null;
}

export interface TileProblems {
  power: number;
  fans: number;
  display: number;
  gamepad: number;
  sound: number;
}

const count = (...red: boolean[]) => red.filter(Boolean).length;

/** How many things each tile's screen shows red. */
export function tileProblems(sources: ProblemSources): TileProblems {
  const { settings, conflicts, gyro, triggers, buttons } = sources;
  // Off, Steam sets the TDP by the user's choice; then neither the slider nor other writers matter.
  // Left to Steam by "restore everything", the TDP drops again until the user decides.
  const ownTdp = conflicts.power === null && settings.manageTdp === true;
  return {
    power: count(
      conflicts.power !== null,
      conflicts.power === null && conflicts.boost !== null,
      conflicts.power === null && unset(settings.manageTdp),
      ownTdp && sources.steamTdpSlider,
      ownTdp && sources.contested,
    ),
    fans: count(conflicts.fans !== null),
    display: count(conflicts.saturation !== null, conflicts.lighting !== null),
    gamepad: count(
      conflicts.vibration !== null,
      conflicts.triggers === null
        ? triggers === "available" && unset(settings.triggerRumble)
        : separateTriggerOwner(conflicts) !== null,
      drives(buttons, "quick_access") && unset(settings.qamAssist),
      sources.overlayMenu === true && unset(settings.overlayFix),
      gyro !== null && gyroProblem(gyro, settings.gyroFix),
      drives(buttons, "armoury_crate") && buttonUnset(settings.armouryCrate, settings.armouryCrateHold),
    ),
    sound: count(conflicts.sound !== null, sources.clockCrackle === true && unset(settings.clockFix)),
  };
}
