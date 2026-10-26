// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it, vi } from "vitest";

import { cycleOverlay, nextOverlayLevel } from "./overlay";

// Steam's performance settings store, found among Steam's modules only inside Steam. Like Steam's,
// it takes a new level only later, when the client reports it back.
const steam = vi.hoisted(() => {
  const store = {
    msgSettingsGlobal: { perf_overlay_level: 3 },
    requested: [] as number[],
    SetPerfOverlayLevel(level: number) {
      this.requested.push(level);
    },
  };
  // The module as Steam ships it: the tab's hook, the store class with its static Get, others.
  const module = {
    aS: function useOverlayLevel() {
      return "SetPerfOverlayLevel";
    },
    Hn: Object.assign(() => store, { Get: () => store }),
    mM: () => undefined,
  };
  return { store, module };
});

vi.mock("@decky/ui", () => ({
  findModuleByExport: (filter: (value: unknown) => boolean) =>
    Object.values(steam.module).some(filter) ? steam.module : undefined,
}));

const HIDDEN = 0;
const BASIC = 1;
const MEDIUM = 2;
const FULL = 3;
const MINIMAL = 4;

describe("performance overlay", () => {
  it("goes through the levels as Steam's slider shows them, then off", () => {
    expect([HIDDEN, MINIMAL, BASIC, MEDIUM, FULL].map(nextOverlayLevel)).toEqual([MINIMAL, BASIC, MEDIUM, FULL, HIDDEN]);
  });

  it("turns an unknown level off", () => {
    expect(nextOverlayLevel(7)).toBe(HIDDEN);
  });

  it("sets the next level, and goes on from it while Steam has not taken it yet", () => {
    expect(cycleOverlay()).toBe(true);
    cycleOverlay();

    expect(steam.store.requested).toEqual([HIDDEN, MINIMAL]);
  });
});
