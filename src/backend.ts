// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { callable } from "@decky/api";

// Mirrors the dataclasses in py_modules/origami (origami.wire converts keys to camelCase).

export interface Device {
  board: string | null;
  product: string | null;
  model: string | null;
}

export interface Versions {
  os: {
    id: string | null;
    name: string | null;
    versionId: string | null;
    imageVersion: string | null;
    buildId: string | null;
  };
  kernel: string | null;
  inputplumber: string | null;
  decky: string | null;
}

/** A button of the console ORIGAMI may drive (origami.buttons.Button). */
export type ConsoleButton = "quick_access" | "armoury_crate" | "armoury_crate_hold";

export interface Info {
  version: string;
  device: Device;
  versions: Versions;
  /** The buttons ORIGAMI may drive here; the system keeps the others (both of the ROG Ally's). */
  buttons: ConsoleButton[];
  /** ORIGAMI processes this console's speakers: it has their protection. */
  sound: boolean;
  /** The system has an overlay menu of its own that ORIGAMI can keep in sight. */
  overlayMenu: boolean;
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
    /** The highest sustained limit the firmware takes on the supply in use: 35 W on the Ally X. */
    tdpTopW: number | null;
    /** The highest on the battery, where known: 25 W on the ROG Ally, so no more to allow there. */
    batteryTdpTopW: number | null;
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

/** Lighting of the stick rings (origami.lighting.Lighting); colours are 0xRRGGBB. */
export interface Lighting {
  /** Off keeps the rings dark; the other fields wait for the next time it is on. */
  enabled: boolean;
  mode: LightMode;
  left: number;
  right: number;
  speed: LightSpeed;
  /** Percent, 5–100: smooth for ORIGAMI's colours, three levels for rainbow and spiral. */
  brightness: number;
}

/** ORIGAMI's curve for both fans (origami.fans.FanCurve); speeds in percent at 30–90 °C. */
export interface FanCurve {
  /** Off gives the fans back to the firmware; the points wait for the next time it is on. */
  enabled: boolean;
  points: number[];
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
export type TriggerLevel = "soft" | "medium" | "strong";

/** Rumble of the impulse triggers (origami.triggers.TriggerRumble). */
export interface TriggerRumble {
  /** Off keeps the motors still; the triggers and the level wait until it is on again. */
  enabled: boolean;
  triggers: Triggers;
  level: TriggerLevel;
  /** One short tap on each shot instead of steady rumble. */
  taps: boolean;
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

/** A game's own power settings, made as a copy of the general ones (origami.power.GamePower). */
export interface GamePower {
  /** Steam's app id; non-Steam shortcuts have one as well. */
  appId: number;
  /** The game's name as Steam showed it, for the list while the game is not running. */
  name: string;
  power: Power;
  /** The game runs with this profile; off, it runs with the general settings and this waits. */
  active: boolean;
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

export type SoundVolume = 0 | 4 | 6;
export type SoundWidth = "off" | "moderate" | "strong";

/** ORIGAMI's filter in front of the speakers (origami.sound.Sound). */
export interface Sound {
  enabled: boolean;
  volumeDb: SoundVolume;
  width: SoundWidth;
  voices: boolean;
}

/** A game's own sound, made as a copy of the general one (origami.sound.GameSound). */
export interface GameSound {
  /** Steam's app id; non-Steam shortcuts have one as well. */
  appId: number;
  /** The game's name as Steam showed it, for the list while the game is not running. */
  name: string;
  sound: Sound;
  /** The game runs with this sound; off, it runs with the general one and this waits. */
  active: boolean;
}

/** What the Sound screen shows besides the settings (origami.blocks.sound.SoundState). */
export interface SoundState {
  /** There is a speaker sink: PipeWire runs and the console has its speakers. */
  speakers: boolean;
  /** Headphones play on the speakers' sink, so the filter waits for the speakers. */
  headphones: boolean;
  running: boolean;
  /** Another program whose filter processes the speakers now, found in PipeWire; null when none. */
  owner: string | null;
  /** The filter did not stay up after its last start, and ORIGAMI waits to try again. */
  failed: boolean;
  /** The crackle after sleep happens here, so the screen offers its fix. */
  clockFix: boolean;
}

/** What the gyroscope's axes need here (origami.gyro.GyroState). */
export type GyroState = "unavailable" | "fixed_in_system" | "foreign" | "wrong" | "fixed" | "outdated";

export interface Settings {
  language: LanguageSetting;
  /** ORIGAMI has its own quick access tab besides its place inside Decky. */
  qamTab: boolean;
  /** Steam tab that ORIGAMI's tab stands before; -1 on top, null at the end. */
  qamTabBefore: number | null;
  /** Once a day, as ORIGAMI opens, it asks GitHub for a newer release; off, only on a press. */
  updateCheck: boolean;
  /** ORIGAMI opens the quick access menu when Steam misses a press of its button; null until the user sets it. */
  qamAssist: boolean | null;
  /** ORIGAMI turns the gyroscope's yaw the right way for Steam; null until the user sets it. */
  gyroFix: boolean | null;
  /** ORIGAMI steps the clock after sleep where the hardware clock keeps local time; null until set. */
  clockFix: boolean | null;
  /** ORIGAMI keeps the system's overlay menu in sight after its first time; null until set. */
  overlayFix: boolean | null;
  /** Null until the user sets it; the controller keeps its own lighting until then. */
  lighting: Lighting | null;
  /** Screen saturation in percent (100 = sRGB); null until the user sets it. */
  saturation: number | null;
  /** Null until the user sets it; the controller keeps its own strength until then. */
  vibration: Vibration | null;
  /** Null until the user chooses; the triggers stay still until then. */
  triggerRumble: TriggerRumble | null;
  /** What a short press of the upper left button does; nothing reaches Steam from it. Null until set: nothing. */
  armouryCrate: ButtonAction | null;
  /** What holding the upper left button does, besides the L5 Steam gets from it. Null until set: nothing. */
  armouryCrateHold: ButtonAction | null;
  /**
   * ORIGAMI owns the TDP and writes it again whenever it drops; off, Steam sets it. Null after
   * "restore everything" until the user decides: off all the same, but a problem.
   */
  manageTdp: boolean | null;
  power: Power;
  /** The TDP may go over 25 W on the battery too. */
  batteryHighTdp: boolean;
  /** Games with power settings of their own, one profile each. */
  gamePower: GamePower[];
  /** Null until the user switches it on; the fans run the firmware's own curve until then. */
  fans: FanCurve | null;
  /** Null until the user switches it on; the speakers play as the system has them until then. */
  sound: Sound | null;
  gameSound: GameSound[];
}

/** Enabled plugins that drive hardware ORIGAMI also drives. */
export interface Conflicts {
  lighting: string | null;
  saturation: string | null;
  vibration: string | null;
  triggers: string | null;
  power: string | null;
  /** The plugin that holds the CPU boost: one that sets the whole power, or the boost alone (Ally Fix). */
  boost: string | null;
  fans: string | null;
  /** A plugin with a filter of its own in front of the speakers. */
  sound: string | null;
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
  restoreAll: callable<[], Settings>("restore_all"),
  previewLighting: callable<[lighting: Lighting]>("preview_lighting"),
  testVibration: callable("test_vibration"),
  paste: callable<[], boolean>("paste"),
  getTriggerState: callable<[], TriggerState>("get_trigger_state"),
  testTriggerRumble: callable("test_trigger_rumble"),
  getGyro: callable<[], GyroState>("get_gyro"),
  getSaturation: callable<[], number | null>("get_saturation"),
  restoreSaturation: callable("restore_saturation"),
  getPower: callable<[], HeldPower>("get_power"),
  getSound: callable<[], SoundState>("get_sound"),
  gameStarted: callable("game_started"),
  setGame: callable<[appId: number | null]>("set_game"),
  setSteamTdpLimit: callable<[on: boolean]>("set_steam_tdp_limit"),
};
