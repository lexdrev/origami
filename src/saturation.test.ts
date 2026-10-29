// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { afterEach, describe, expect, it, vi } from "vitest";

import { presetOf, refreshSaturation, saturation, setSaturation } from "./saturation";

// The backend and the settings call, which reach Decky only inside Steam.
const fake = vi.hoisted(() => {
  const state: { shown: number | null; saved: number[] } = { shown: 100, saved: [] };
  return state;
});

vi.mock("./backend", () => ({
  backend: { getSaturation: () => Promise.resolve(fake.shown) },
}));

vi.mock("./state", () => ({
  updateSettings: (changes: { saturation: number }) => {
    fake.saved.push(changes.saturation);
    fake.shown = changes.saturation;
    return Promise.resolve();
  },
}));

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

afterEach(() => {
  saturation.set(null);
  fake.shown = 100;
  fake.saved = [];
});

describe("saturation", () => {
  it("shows what gamescope has now", async () => {
    fake.shown = 150;

    await refreshSaturation();

    expect(saturation.get()).toBe(150);
  });

  it("is not there without gamescope", async () => {
    fake.shown = null;

    await refreshSaturation();

    expect(saturation.get()).toBeNull();
  });

  it("is saved within 0–200%, only the newest of quick changes", async () => {
    setSaturation(110);
    setSaturation(120);
    setSaturation(250);
    await settle();
    await settle();

    expect(fake.saved).toEqual([110, 200]);
    expect(saturation.get()).toBe(200);
  });

  it("names the preset a value matches", () => {
    expect(presetOf(150)?.id).toBe("vivid");
    expect(presetOf(200)?.id).toBe("max");
    expect(presetOf(140)).toBeUndefined();
  });
});
