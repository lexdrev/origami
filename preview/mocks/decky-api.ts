// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

// Browser stand-in for @decky/api with readings taken from the console (HARDWARE.md).

import type {
  Change,
  Conflicts,
  HeldPower,
  Info,
  Settings,
  SharpnessGameState,
  SharpnessState,
  SoundState,
  Telemetry,
} from "../../src/backend";

const info: Info = {
  version: "1.0.0",
  device: { board: "RC73XA", product: "ROG Xbox Ally X RC73XA_RC73XA", model: "ROG Xbox Ally X" },
  versions: {
    os: {
      id: "bazzite",
      name: "Bazzite",
      versionId: "45",
      imageVersion: "45.20261104",
      buildId: "Stable (F45.20261104)",
    },
    kernel: "7.2.15-ogc1.1.fc45.x86_64",
    inputplumber: "0.83.1",
    decky: "v3.3.1",
  },
  buttons: ["armoury_crate", "armoury_crate_hold", "quick_access"],
  sound: true,
  fanHold: true,
  overlayMenu: true,
  sharpness: true,
};
const query = new URLSearchParams(location.search);
// "?nohold" is a console whose fans hold no temperature: the Fans screen has the curve alone.
if (query.has("nohold")) info.fanHold = false;
// "?nosharpness" is a system without the sharpening layer: the main screen has no Service tile.
if (query.has("nosharpness")) info.sharpness = false;

let settings: Settings = {
  language: "auto",
  qamTab: true,
  qamTabBefore: 7,
  updateCheck: false,
  qamAssist: null,
  gyroFix: null,
  clockFix: null,
  overlayFix: null,
  lighting: null,
  saturation: null,
  vibration: null,
  triggerRumble: null,
  armouryCrate: null,
  armouryCrateHold: null,
  manageTdp: true,
  power: { tdp: 17, headroom: true, cpuBoost: null },
  batteryHighTdp: false,
  gamePower: [
    {
      appId: 1920490,
      name: "The Outer Worlds: Spacer's Choice Edition",
      power: { tdp: 15, headroom: true, cpuBoost: true },
      active: true,
    },
    { appId: 1091500, name: "Cyberpunk 2077", power: { tdp: 25, headroom: true, cpuBoost: null }, active: true },
    { appId: 990080, name: "Hogwarts Legacy", power: { tdp: 20, headroom: false, cpuBoost: false }, active: false },
  ],
  // "?hold" starts with the fans holding a temperature.
  fans: { enabled: true, points: [0, 10, 25, 40, 55, 75, 100], hold: query.has("hold"), target: 60 },
  sound: { enabled: true, volumeDb: 4, width: "moderate", voices: true },
  gameSound: [
    {
      appId: 1920490,
      name: "The Outer Worlds: Spacer's Choice Edition",
      sound: { enabled: true, volumeDb: 6, width: "off", voices: true },
      active: true,
    },
    {
      appId: 990080,
      name: "Hogwarts Legacy",
      sound: { enabled: false, volumeDb: 4, width: "moderate", voices: true },
      active: false,
    },
  ],
  sharpness: { enabled: true, strength: 40 },
  gameSharpness: [
    {
      appId: 1920490,
      name: "The Outer Worlds: Spacer's Choice Edition",
      sharpness: { enabled: true, strength: 70 },
      active: true,
    },
    { appId: 1091500, name: "Cyberpunk 2077", sharpness: { enabled: false, strength: 40 }, active: true },
  ],
};
// Steam's value, as gamescope shows it on the console while nothing else sets it.
const STEAM_SATURATION = 100;
const conflicts: Conflicts = {
  lighting: null,
  saturation: null,
  vibration: null,
  triggers: null,
  power: null,
  boost: null,
  fans: null,
  // "?soundplugin" stands for another plugin with a filter in front of the speakers.
  sound: query.has("soundplugin") ? "Sound Plugin" : null,
  // "?sharpplugin" stands for another plugin that sets the sharpening layer itself.
  sharpness: query.has("sharpplugin") ? "Sharpness Plugin" : null,
};
const changes: Change[] = [
  { module: "power", key: "tdp", original: null },
  { module: "fans", key: "curve", original: null },
  { module: "gamepad", key: "vibration", original: [100, 100] },
];

// Settings.restored in the backend: nothing of the system is left to ORIGAMI.
function restoreAll(): Settings {
  const withoutBoost = (power: Settings["power"]) => ({ ...power, cpuBoost: null });
  settings = {
    ...settings,
    qamAssist: null,
    gyroFix: null,
    clockFix: null,
    overlayFix: null,
    lighting: null,
    saturation: null,
    vibration: null,
    triggerRumble: null,
    armouryCrate: null,
    armouryCrateHold: null,
    manageTdp: null,
    power: withoutBoost(settings.power),
    gamePower: settings.gamePower.map((game) => ({ ...game, power: withoutBoost(game.power) })),
    fans: null,
    sound: null,
    gameSound: settings.gameSound.map((game) => ({ ...game, active: false })),
    sharpness: null,
    gameSharpness: settings.gameSharpness.map((game) => ({ ...game, active: false })),
  };
  changes.splice(0);
  return settings;
}

// The curve the backend keeps in the firmware (origami.fans.hold_curve), at the level it starts from.
function holdCurve(target: number): [number, number][] {
  const net = [35, 50, 65, 80, 90].map((least, step): [number, number] => [target + 4 + step, Math.max(40, least)]);
  return [[30, 40], ...net, [target + 10, 100], [100, 100]];
}

// "?battery" takes the charger away: the battery tells how long it lasts.
function telemetry(): Telemetry {
  const wobble = Math.sin(Date.now() / 4000);
  const onBattery = query.has("battery");
  return {
    power: {
      tdpLimitW: settings.power.tdp,
      tdpTopW: 35,
      batteryTdpTopW: 35,
      packagePowerW: settings.power.tdp - 0.1 + wobble * 0.3,
      cpuBoost: settings.power.cpuBoost ?? false,
      onBattery,
      battery: onBattery
        ? { percent: 54, charging: false, minutesLeft: 95, untilPct: 10, drainW: 29.4 + wobble * 0.2, capacityPct: 93 }
        : { percent: 68, charging: true, minutesLeft: null, untilPct: null, drainW: null, capacityPct: 93 },
    },
    fans: {
      speedsRpm: [5200 + Math.round(wobble * 80), 5300],
      cpuTempC: 63.4,
      gpuTempC: 61,
      holdCurve: settings.fans?.enabled && settings.fans.hold ? holdCurve(settings.fans.target) : null,
    },
    gamepad: { vibrationPct: [100, 100] },
  };
}

const routes: Record<string, (...args: never[]) => unknown> = {
  get_info: () => info,
  get_telemetry: telemetry,
  get_settings: () => settings,
  update_settings: (update: Partial<Settings>) => (settings = { ...settings, ...update }),
  get_changes: () => changes,
  get_conflicts: () => conflicts,
  restore_all: restoreAll,
  get_saturation: () => settings.saturation ?? STEAM_SATURATION,
  restore_saturation: () => undefined,
  test_vibration: () => undefined,
  get_trigger_state: () => "available",
  test_trigger_rumble: () => undefined,
  get_gyro: () => (settings.gyroFix ? "fixed" : "wrong"),
  get_power: heldPower,
  get_sound: soundState,
  game_started: () => undefined,
  set_game: () => undefined,
  game_starting: () => undefined,
  get_sharpness: sharpnessState,
  set_steam_tdp_limit: () => undefined,
};

// The limits as asus-armoury takes them on the charger: the boost from 14 W, the peak from 19 W.
function heldPower(): HeldPower {
  const { tdp, headroom } = settings.power;
  if (!settings.manageTdp) return { limits: null, batteryCapped: false, contested: false };
  const sppt = Math.min(Math.max(headroom ? tdp + 4 : tdp, 14), 45);
  const fppt = Math.min(Math.max(headroom ? tdp + 9 : tdp, 19), 55);
  return { limits: { spl: tdp, sppt, fppt }, batteryCapped: false, contested: false };
}

// "?headphones" puts headphones on the speakers' sink, "?localclock" a hardware clock in local time;
// "?nospeakers" takes the speaker sink away, "?soundfailed" is a filter that did not stay up and
// "?soundstarting" one that still comes up; "?soundfilter" is a program outside Decky that processes
// the speakers.
function soundState(): SoundState {
  const speakers = !query.has("nospeakers");
  const headphones = speakers && query.has("headphones");
  const failed = query.has("soundfailed");
  const wanted = settings.sound?.enabled === true && conflicts.sound === null && speakers && !headphones;
  const running = wanted && !failed && !query.has("soundstarting");
  const owner = query.has("soundfilter") ? "EasyEffects" : null;
  return {
    speakers,
    headphones,
    running: running && owner === null,
    owner,
    failed: wanted && failed,
    clockFix: query.has("localclock"),
  };
}

// With "?game" the stand runs the game of the first profile. "?sharppending" is a sharpness changed
// since that game started (its strength, or switched off), "?sharpstarting" one switched on since, "?sharpmissing" a game that did not load the layer, "?sharpblocked" one whose
// launch options set the layer themselves.
// "?sharpblocked" is a game started through another plugin's wrapper, "?sharplaunch" one whose launch
// options set the layer by themselves; either way the sharpness there is not ORIGAMI's.
function sharpnessState(): SharpnessState {
  const taken = query.has("game") && (query.has("sharpblocked") || query.has("sharplaunch"));
  if (!taken) return { game: sharpnessGame(), owner: null, sharpening: null, companion: null };
  const owner = query.has("sharpblocked") ? "Frame Plugin" : null;
  return { game: "managed", owner, sharpening: owner && "shaders", companion: "Other Frame Plugin" };
}

function sharpnessGame(): SharpnessGameState {
  if (!query.has("game")) return "no_game";
  const own = settings.gameSharpness.find((game) => game.appId === 1920490 && game.active);
  const used = own?.sharpness ?? settings.sharpness;
  if (query.has("sharppending")) return used?.enabled ? "new_strength" : "turning_off";
  if (query.has("sharpstarting") && used?.enabled) return "turning_on";
  if (!used?.enabled) return "off";
  return query.has("sharpmissing") ? "missing" : "working";
}

// "?nobackend" in the address stands for a backend that never answers, as on a Decky Loader too old for it.
const silent = query.has("nobackend");

export function callable(route: string) {
  return async (...args: never[]): Promise<unknown> => {
    if (silent) return new Promise(() => undefined);
    await new Promise((resolve) => setTimeout(resolve, 30));
    const handler = routes[route];
    if (handler === undefined) throw new Error(`No mock for ${route}`);
    return handler(...args);
  };
}

export const useQuickAccessVisible = () => true;

// The stand has no backend events; QAM assist never hears a press.
export const addEventListener = <T>(_event: string, listener: T) => listener;
export const removeEventListener = () => undefined;

export const definePlugin = <T>(factory: () => T) => factory;
