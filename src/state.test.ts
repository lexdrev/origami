// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { afterEach, describe, expect, it, vi } from "vitest";

import type { Settings, Vibration } from "./backend";
import { actionError, setVibration, settings } from "./state";

// The backend, which Decky reaches only inside Steam; it keeps what it accepts.
const fake = vi.hoisted(() => {
  const state: { refuse: boolean; sent: (Vibration | null | undefined)[]; kept: Vibration | null } = {
    refuse: false,
    sent: [],
    kept: null,
  };
  return state;
});

vi.mock("./backend", () => ({
  backend: {
    updateSettings: (changes: Partial<Settings>) => {
      fake.sent.push(changes.vibration);
      if (fake.refuse) return Promise.reject(new Error("Vibration Plugin sets the vibration strength"));
      fake.kept = changes.vibration ?? null;
      return Promise.resolve({ vibration: fake.kept });
    },
    getSettings: () => Promise.resolve({ vibration: fake.kept }),
  },
}));

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
const shown = () => {
  const current = settings.get();
  return current.status === "ready" ? current.value.vibration : undefined;
};

afterEach(() => {
  settings.set({ status: "loading" });
  actionError.set(null);
  Object.assign(fake, { refuse: false, sent: [], kept: null });
});

describe("vibration strength", () => {
  const loaded = () => {
    settings.set({ status: "ready", value: { vibration: null } as Settings });
  };

  it("shows a change at once and saves only the newest of quick ones", async () => {
    loaded();

    setVibration({ enabled: true, left: 55, right: 55 });
    setVibration({ enabled: true, left: 60, right: 60 });
    setVibration({ enabled: true, left: 65, right: 65 });

    expect(shown()).toEqual({ enabled: true, left: 65, right: 65 });
    await settle();
    await settle();
    expect(fake.sent).toEqual([
      { enabled: true, left: 55, right: 55 },
      { enabled: true, left: 65, right: 65 },
    ]);
    expect(shown()).toEqual({ enabled: true, left: 65, right: 65 });
  });

  it("goes back to the saved strength when the backend refuses a change", async () => {
    loaded();
    fake.refuse = true;

    setVibration({ enabled: true, left: 30, right: 30 });
    await settle();
    await settle();

    expect(shown()).toBeNull();
    expect(actionError.get()).toMatch("Vibration Plugin");
  });

  it("waits for the settings to load", () => {
    setVibration({ enabled: true, left: 30, right: 30 });

    expect(settings.get()).toEqual({ status: "loading" });
    expect(fake.sent).toEqual([]);
  });
});
