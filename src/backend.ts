// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { callable } from "@decky/api";

// Mirrors the dataclasses in py_modules/origami (origami.wire converts keys to camelCase).

export interface Device {
  board: string | null;
  product: string | null;
  model: string | null;
}

export interface Versions {
  os: { name: string | null; versionId: string | null; imageVersion: string | null };
  kernel: string | null;
  inputplumber: string | null;
  decky: string | null;
}

export interface Info {
  version: string;
  device: Device;
  versions: Versions;
}

export interface Telemetry {
  power: { tdpLimitW: number | null; packagePowerW: number | null; cpuBoost: boolean | null };
  fans: { speedsRpm: number[]; cpuTempC: number | null; gpuTempC: number | null };
  gamepad: { vibrationPct: [number, number] | null };
}

export type LanguageSetting = "auto" | "ru" | "en";

export type LightMode = "static" | "breathing" | "rainbow" | "spiral";
export type LightSpeed = "slow" | "medium" | "fast";
export type LightBrightness = "low" | "medium" | "high";

/** Lighting of the stick rings (origami.lighting.Lighting); colours are 0xRRGGBB. */
export interface Lighting {
  /** Off keeps the rings dark; the other fields wait for the next time it is on. */
  enabled: boolean;
  mode: LightMode;
  left: number;
  right: number;
  speed: LightSpeed;
  brightness: LightBrightness;
}

/** Handle vibration (origami.vibration.Vibration); strengths in percent. */
export interface Vibration {
  /** Off keeps the handles still; the strengths wait for the next time it is on. */
  enabled: boolean;
  left: number;
  right: number;
}

/** Which impulse triggers follow a game's rumble (origami.triggers.Triggers). */
export type Triggers = "right" | "both";

/** How strongly the triggers rumble (origami.triggers.TriggerLevel). */
export type TriggerLevel = "soft" | "medium" | "strong" | "max";

/** Rumble of the impulse triggers (origami.triggers.TriggerRumble). */
export interface TriggerRumble {
  /** Off keeps the motors still; the triggers and the level wait until it is on again. */
  enabled: boolean;
  triggers: Triggers;
  level: TriggerLevel;
}

/** Whether the triggers here have motors ORIGAMI can rumble (origami.triggers.TriggerState). */
export type TriggerState = "unavailable" | "available";

/** What ORIGAMI does on a press of a button it may drive (origami.buttons.ButtonAction). */
export type ButtonAction =
  | "none"
  | "origami"
  | "quick_access"
  | "performance"
  | "overlay"
  | "lighting"
  | "screenshot"
  | "keyboard"
  | "l5"
  | "magnifier"
  | "close_game";

/** What the gyroscope's axes need here (origami.gyro.GyroState). */
export type GyroState = "unavailable" | "fixed_in_system" | "foreign" | "wrong" | "fixed" | "outdated";

export interface Settings {
  language: LanguageSetting;
  /** ORIGAMI has its own quick access tab besides its place inside Decky. */
  qamTab: boolean;
  /** Steam tab that ORIGAMI's tab stands before; -1 on top, null at the end. */
  qamTabBefore: number | null;
  /** ORIGAMI opens the quick access menu when Steam misses a press of its button. */
  qamAssist: boolean;
  /** ORIGAMI turns the gyroscope's yaw the right way for Steam. */
  gyroFix: boolean;
  /** Null until the user sets it; the controller keeps its own lighting until then. */
  lighting: Lighting | null;
  /** Screen saturation in percent (100 = sRGB); null until the user sets it. */
  saturation: number | null;
  /** Null until the user sets it; the controller keeps its own strength until then. */
  vibration: Vibration | null;
  /** Null until the user chooses; the triggers stay still until then. */
  triggerRumble: TriggerRumble | null;
  /** What a short press of the upper left button does; nothing reaches Steam from it. */
  armouryCrate: ButtonAction;
  /** What holding the upper left button does, besides the L5 Steam gets from it. */
  armouryCrateHold: ButtonAction;
}

/** Enabled plugins that drive hardware ORIGAMI also drives. */
export interface Conflicts {
  lighting: string | null;
  saturation: string | null;
  vibration: string | null;
  triggers: string | null;
}

export interface Change {
  module: string;
  key: string;
  original: unknown;
}

export const backend = {
  getInfo: callable<[], Info>("get_info"),
  getTelemetry: callable<[], Telemetry>("get_telemetry"),
  getSettings: callable<[], Settings>("get_settings"),
  updateSettings: callable<[changes: Partial<Settings>], Settings>("update_settings"),
  getChanges: callable<[], Change[]>("get_changes"),
  getConflicts: callable<[], Conflicts>("get_conflicts"),
  previewLighting: callable<[lighting: Lighting]>("preview_lighting"),
  testVibration: callable("test_vibration"),
  getTriggerState: callable<[], TriggerState>("get_trigger_state"),
  testTriggerRumble: callable("test_trigger_rumble"),
  getGyro: callable<[], GyroState>("get_gyro"),
  getSaturation: callable<[], number | null>("get_saturation"),
  restoreSaturation: callable("restore_saturation"),
};
