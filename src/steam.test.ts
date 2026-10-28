// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { afterEach, describe, expect, it, vi } from "vitest";

import { readSteamTdpLimit } from "./steam";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Steam's TDP limit", () => {
  it("is the SteamOS slider of Steam's client settings, in the performance profile", () => {
    const settings = { steamos_tdp_limit_enabled: true, steamos_tdp_limit: 20, steamos_cec_enabled: false };
    vi.stubGlobal("settingsStore", {
      clientSettings: { ...settings, steamos_platform_performance_profile: "performance" },
    });
    expect(readSteamTdpLimit()).toEqual({ enabled: true, watts: 20 });

    // In balanced steamos-manager refuses Steam's TDP: the slider sets nothing.
    vi.stubGlobal("settingsStore", { clientSettings: { ...settings, steamos_platform_performance_profile: "balanced" } });
    expect(readSteamTdpLimit()).toEqual({ enabled: false, watts: 20 });
  });

  it("is off when Steam has never set it, and unknown without the store", () => {
    vi.stubGlobal("settingsStore", { clientSettings: {} });
    expect(readSteamTdpLimit()).toEqual({ enabled: false, watts: null });

    vi.stubGlobal("settingsStore", undefined);
    expect(readSteamTdpLimit()).toBeNull();
  });
});
