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

export interface Settings {
  language: LanguageSetting;
  /** ORIGAMI has its own quick access tab besides its place inside Decky. */
  qamTab: boolean;
  /** Steam tab that ORIGAMI's tab stands before; -1 on top, null at the end. */
  qamTabBefore: number | null;
  /** ORIGAMI opens the quick access menu when Steam misses a press of its button. */
  qamAssist: boolean;
  /** Null until the user sets it; the controller keeps its own lighting until then. */
  lighting: Lighting | null;
  /** Screen saturation in percent (100 = sRGB); null until the user sets it. */
  saturation: number | null;
}

/** Enabled plugins that drive hardware ORIGAMI also drives. */
export interface Conflicts {
  lighting: string | null;
  saturation: string | null;
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
  getSaturation: callable<[], number | null>("get_saturation"),
  restoreSaturation: callable("restore_saturation"),
};
