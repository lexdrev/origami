// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { afterEach, describe, expect, it, vi } from "vitest";

import { en } from "./i18n/en";
import { ru } from "./i18n/ru";
import { batteryTexts, limitsFor, presetOf, steamTdpSlider, watchSteamTdpLimit } from "./power";

// The backend and Steam's performance store, which exist only inside Steam.
const fake = vi.hoisted(() => {
  const state: { steam: boolean | null; reported: boolean[] } = { steam: null, reported: [] };
  return state;
});

vi.mock("./backend", () => ({
  backend: {
    setSteamTdpLimit: (on: boolean) => {
      fake.reported.push(on);
      return Promise.resolve();
    },
  },
}));

vi.mock("./steam", () => ({ readSteamTdpSlider: () => fake.steam }));

afterEach(() => {
  vi.useRealTimers();
  fake.steam = null;
  fake.reported = [];
  steamTdpSlider.set(null);
});

const NBSP = "\u00a0";

describe("power", () => {
  it("knows the presets by their watts, and any other TDP as custom", () => {
    expect(presetOf(17)?.id).toBe("balance");
    expect(presetOf(25)?.id).toBe("turbo");
    expect(presetOf(20)).toBeUndefined();
  });

  it("shows the factory's headroom above the TDP, within what the firmware takes", () => {
    expect(limitsFor({ tdp: 17, headroom: true, cpuBoost: null })).toEqual({ spl: 17, sppt: 21, fppt: 26 });
    expect(limitsFor({ tdp: 35, headroom: true, cpuBoost: null })).toEqual({ spl: 35, sppt: 39, fppt: 44 });
    expect(limitsFor({ tdp: 7, headroom: true, cpuBoost: null })).toEqual({ spl: 7, sppt: 13, fppt: 19 });
  });

  it("without the headroom keeps all three at the TDP above the firmware's lowest", () => {
    expect(limitsFor({ tdp: 20, headroom: false, cpuBoost: null })).toEqual({ spl: 20, sppt: 20, fppt: 20 });
    expect(limitsFor({ tdp: 10, headroom: false, cpuBoost: null })).toEqual({ spl: 10, sppt: 13, fppt: 19 });
  });

  it("tells the charge, what the battery does and its capacity", () => {
    const battery = { percent: 54, charging: false, minutesLeft: 110, capacityPct: 93 };

    expect(batteryTexts(battery, ru)).toEqual({ percent: "54%", state: `~1${NBSP}ч${NBSP}50${NBSP}мин`, capacity: "93%" });
    expect(batteryTexts({ ...battery, minutesLeft: 45 }, en).state).toBe(`~45${NBSP}min`);
    expect(batteryTexts({ ...battery, charging: true, minutesLeft: null }, en).state).toBe("Charging");
    expect(batteryTexts({ percent: null, charging: false, minutesLeft: null, capacityPct: null }, en)).toEqual({
      percent: "—",
      state: null,
      capacity: null,
    });
  });
});

describe("Steam's TDP slider", () => {
  it("reaches the backend once at the start and then only when it is switched", async () => {
    vi.useFakeTimers();
    fake.steam = false;
    const stop = watchSteamTdpLimit();
    await vi.advanceTimersByTimeAsync(6000);
    expect(fake.reported).toEqual([false]);

    fake.steam = true;
    await vi.advanceTimersByTimeAsync(500);
    expect(fake.reported).toEqual([false, true]);
    expect(steamTdpSlider.get()).toBe(true);

    stop();
    fake.steam = false;
    await vi.advanceTimersByTimeAsync(4000);
    expect(fake.reported).toEqual([false, true]);
  });

  it("counts as off where Steam has no store ORIGAMI knows", async () => {
    vi.useFakeTimers();
    const stop = watchSteamTdpLimit();
    await vi.advanceTimersByTimeAsync(0);
    stop();

    expect(fake.reported).toEqual([false]);
    expect(steamTdpSlider.get()).toBeNull();
  });
});
