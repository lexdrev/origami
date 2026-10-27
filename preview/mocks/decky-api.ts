// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

// Browser stand-in for @decky/api with readings taken from the console (HARDWARE.md).

import type { Change, Conflicts, Info, Settings, Telemetry } from "../../src/backend";

const info: Info = {
  version: "0.1.0",
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
  qamAssist: false,
  gyroFix: false,
  lighting: null,
  saturation: null,
  vibration: null,
  armouryCrate: "none",
  armouryCrateHold: "none",
};
// Steam's value, as gamescope shows it on the console without vibrantDeck.
const STEAM_SATURATION = 100;
const conflicts: Conflicts = { lighting: null, saturation: null, vibration: null };
const changes: Change[] = [];

function telemetry(): Telemetry {
  const wobble = Math.sin(Date.now() / 4000);
  return {
    power: { tdpLimitW: 17, packagePowerW: 16.9 + wobble * 0.3, cpuBoost: false },
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
  get_saturation: () => settings.saturation ?? STEAM_SATURATION,
  restore_saturation: () => undefined,
  test_vibration: () => undefined,
  get_gyro: () => (settings.gyroFix ? "fixed" : "wrong"),
};

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
