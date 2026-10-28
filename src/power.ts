// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { backend, type BatteryTelemetry, type Limits, type Power } from "./backend";
import type { Messages } from "./i18n";
import { formatNumber, withUnit } from "./i18n/format";
import { readSteamTdpSlider } from "./steam";
import { createStore } from "./store";

// The TDP and the CPU boost ORIGAMI holds (origami.power). The firmware takes a sustained limit of
// 7–35 W; from the factory it is 17 W with short boosts to 21 and 26 W. On the battery ORIGAMI
// keeps it at 25 W unless the user allows more.

export const MIN_TDP = 7;
export const MAX_TDP = 35;
export const BATTERY_TDP = 25;
export const TDP_STEP = 1;
export const DEFAULT_POWER: Power = { tdp: 17, headroom: true, cpuBoost: null };

/** Sustained limits for the choices; a custom cell after them shows any other. */
export const TDP_PRESETS = [
  { id: "eco", watts: 13 },
  { id: "balance", watts: 17 },
  { id: "turbo", watts: 25 },
] as const;

export type TdpPreset = (typeof TDP_PRESETS)[number];

export function presetOf(tdp: number): TdpPreset | undefined {
  return TDP_PRESETS.find((preset) => preset.watts === tdp);
}

// The firmware's lowest boost and peak on the battery (the charger's boost starts at 14 W).
const LOWEST_SPPT = 13;
const LOWEST_FPPT = 19;
const SPPT_HEADROOM = 4;
const FPPT_HEADROOM = 9;

/**
 * The three limits for a TDP, as the backend writes them on the battery; shown while ORIGAMI does
 * not hold them, when there are none of its own to show.
 */
export function limitsFor({ tdp, headroom }: Power): Limits {
  const clamp = (watts: number, lowest: number, highest: number) => Math.min(Math.max(watts, lowest), highest);
  return {
    spl: tdp,
    sppt: clamp(headroom ? tdp + SPPT_HEADROOM : tdp, LOWEST_SPPT, 45),
    fppt: clamp(headroom ? tdp + FPPT_HEADROOM : tdp, LOWEST_FPPT, 55),
  };
}

export interface BatteryTexts {
  percent: string;
  /** Charging, or the time left; null when neither is known. */
  state: string | null;
  capacity: string | null;
}

/** The line under the screen: the charge and what it does, then the battery's capacity. */
export function batteryTexts(battery: BatteryTelemetry, t: Messages): BatteryTexts {
  const state = battery.charging
    ? t.power.charging
    : battery.minutesLeft !== null
      ? t.power.timeLeft(Math.floor(battery.minutesLeft / 60), battery.minutesLeft % 60)
      : null;
  return {
    percent: battery.percent === null ? t.unknown : `${battery.percent}%`,
    state,
    capacity: battery.capacityPct === null ? null : `${battery.capacityPct}%`,
  };
}

/** Watts as the dial shows the power drawn: one decimal. */
export function formatWatts(watts: number, t: Messages): string {
  return withUnit(formatNumber(watts, t.locale, 1), t.units.watts);
}

/** Steam's TDP slider, on where it writes the TDP, as last seen; null where Steam has no store ORIGAMI knows. */
export const steamTdpSlider = createStore<boolean | null>(null);

/** The screen says so soon after the slider is switched; the backend answers its writes meanwhile. */
const STEAM_LOOK_MS = 500;

/**
 * Starts telling the backend whether Steam's TDP slider is on: ORIGAMI keeps the TDP over it while
 * it manages the TDP, and answers its writes at once (origami.app.set_steam_tdp_limit). Returns the
 * function that stops it.
 */
export function watchSteamTdpLimit(): () => void {
  let reported: boolean | null = null;
  let sending = false;
  const look = () => {
    const slider = readSteamTdpSlider();
    steamTdpSlider.set(slider);
    const on = slider ?? false;
    if (on === reported || sending) return;
    sending = true;
    backend
      .setSteamTdpLimit(on)
      .then(() => {
        reported = on;
      })
      .catch((error: unknown) => {
        console.warn("ORIGAMI: cannot tell the backend about Steam's TDP limit", error);
      })
      .finally(() => {
        sending = false;
      });
  };
  look();
  const timer = setInterval(look, STEAM_LOOK_MS);
  return () => {
    clearInterval(timer);
  };
}

/**
 * Starts telling the backend when a game starts: Steam writes its own limits and the profile
 * meanwhile (BUGS.md, B05), so ORIGAMI writes again. Returns the function that stops it.
 */
export function watchGameStarts(): () => void {
  const registration = window.SteamClient.GameSessions.RegisterForAppLifetimeNotifications((notification) => {
    if (!notification.bRunning) return;
    backend.gameStarted().catch((error: unknown) => {
      console.warn("ORIGAMI: cannot tell the backend that a game started", error);
    });
  });
  return () => {
    registration.unregister();
  };
}
