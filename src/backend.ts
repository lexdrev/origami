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

export interface BatteryTelemetry {
  percent: number | null;
  charging: boolean;
  /** Until empty at the power drawn now; null on the charger or while nothing is drawn. */
  minutesLeft: number | null;
  /** Full charge now against the design's: the battery's wear. */
  capacityPct: number | null;
}

export interface Telemetry {
  power: {
    /** What asus-armoury shows for the supply in use: what was written last, not what the firmware applies. */
    tdpLimitW: number | null;
    packagePowerW: number | null;
    cpuBoost: boolean | null;
    onBattery: boolean;
    battery: BatteryTelemetry | null;
  };
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

/** What the user chose on the Power screen (origami.power.Power). */
export interface Power {
  /** The sustained limit in watts, 7–35. */
  tdp: number;
  /** Short boosts above the TDP, as from the factory; off, all three limits are the TDP. */
  headroom: boolean;
  /** Null until the user chooses; ORIGAMI leaves the boost flag alone until then. */
  cpuBoost: boolean | null;
}

/** The SoC's three power limits in watts (origami.tdp.Limits). */
export interface Limits {
  spl: number;
  sppt: number;
  fppt: number;
}

/** What ORIGAMI holds now (origami.power.HeldPower). */
export interface HeldPower {
  /** ORIGAMI's limits for the supply in use; null while it does not write the TDP. */
  limits: Limits | null;
  /** On the battery the TDP is held at 25 W instead of the one chosen. */
  batteryCapped: boolean;
  /** Something else keeps writing the TDP, so ORIGAMI stopped until the settings change. */
  contested: boolean;
}

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
  /** ORIGAMI owns the TDP and writes it again whenever it drops; off, Steam sets it. */
  manageTdp: boolean;
  power: Power;
  /** The TDP may go over 25 W on the battery too. */
  batteryHighTdp: boolean;
}

/** Enabled plugins that drive hardware ORIGAMI also drives. */
export interface Conflicts {
  lighting: string | null;
  saturation: string | null;
  vibration: string | null;
  triggers: string | null;
  power: string | null;
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
  getPower: callable<[], HeldPower>("get_power"),
  gameStarted: callable("game_started"),
  setSteamTdpLimit: callable<[on: boolean, watts: number | null]>("set_steam_tdp_limit"),
};
