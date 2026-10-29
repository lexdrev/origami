// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

// Browser stand-in for @decky/api with readings taken from the console (HARDWARE.md).

import type { Change, Conflicts, HeldPower, Info, Settings, Telemetry } from "../../src/backend";

const info: Info = {
  version: "1.0.0",
  device: { board: "RC73XA", product: "ROG Xbox Ally X RC73XA_RC73XA", model: "ROG Xbox Ally X" },
  versions: {
    os: { name: "Bazzite", versionId: "44", imageVersion: "44.20261023" },
    kernel: "7.2.9-ogc3.1.fc44.x86_64",
    inputplumber: "0.83.0",
    decky: "v3.3.0",
  },
};

let settings: Settings = {
  language: "auto",
  qamTab: true,
  qamTabBefore: 7,
  qamAssist: null,
  gyroFix: null,
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
  fans: { enabled: true, points: [0, 10, 25, 40, 55, 75, 100] },
};
// Steam's value, as gamescope shows it on the console while nothing else sets it.
const STEAM_SATURATION = 100;
const conflicts: Conflicts = {
  lighting: null,
  saturation: null,
  vibration: null,
  triggers: null,
  power: null,
  fans: null,
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
  };
  changes.splice(0);
  return settings;
}

function telemetry(): Telemetry {
  const wobble = Math.sin(Date.now() / 4000);
  return {
    power: {
      tdpLimitW: settings.power.tdp,
      packagePowerW: settings.power.tdp - 0.1 + wobble * 0.3,
      cpuBoost: settings.power.cpuBoost ?? false,
      onBattery: false,
      battery: { percent: 68, charging: true, minutesLeft: null, capacityPct: 93 },
    },
    fans: { speedsRpm: [4600 + Math.round(wobble * 80), 4700], cpuTempC: 63.4, gpuTempC: 61 },
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
  game_started: () => undefined,
  set_game: () => undefined,
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

export function callable(route: string) {
  return async (...args: never[]): Promise<unknown> => {
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
