// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

// Browser stand-in for @decky/api with readings taken from the console (HARDWARE.md).

import type { Change, Info, Settings, Telemetry } from "../../src/backend";

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

let settings: Settings = { language: "auto" };
const changes: Change[] = [];

function telemetry(): Telemetry {
  const wobble = Math.sin(Date.now() / 4000);
  return {
    power: { tdpLimitW: 17, packagePowerW: 16.9 + wobble * 0.3, cpuBoost: false },
    fans: { speedsRpm: [4600 + Math.round(wobble * 80), 4700], cpuTempC: 63.4, gpuTempC: 61 },
    gamepad: { vibrationPct: [50, 50] },
  };
}

const routes: Record<string, (...args: never[]) => unknown> = {
  get_info: () => info,
  get_telemetry: telemetry,
  get_settings: () => settings,
  update_settings: (update: Partial<Settings>) => (settings = { ...settings, ...update }),
  get_changes: () => changes,
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

export const definePlugin = <T>(factory: () => T) => factory;
