// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { afterEach, describe, expect, it, vi } from "vitest";

import { readSteamLanguage, readSteamTdpSlider } from "./steam";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Steam's language", () => {
  it.each([
    ["german", "de"],
    ["english", "en"],
    ["spanish", "es"],
    ["latam", "es"],
    ["french", "fr"],
    ["russian", "ru"],
    ["schinese", "zh"],
    // Languages ORIGAMI has no words in: traditional Chinese is one of them.
    ["tchinese", "en"],
    ["koreana", "en"],
  ])("%s gives ORIGAMI in %s", async (steam, language) => {
    vi.stubGlobal("window", { SteamClient: { Settings: { GetCurrentLanguage: () => Promise.resolve(steam) } } });
    expect(await readSteamLanguage()).toBe(language);
  });
});

describe("Steam's TDP slider", () => {
  it("is the SteamOS slider of Steam's client settings, in the performance profile", () => {
    const settings = { steamos_tdp_limit_enabled: true, steamos_tdp_limit: 20, steamos_cec_enabled: false };
    vi.stubGlobal("settingsStore", {
      clientSettings: { ...settings, steamos_platform_performance_profile: "performance" },
    });
    expect(readSteamTdpSlider()).toBe(true);

    // In balanced steamos-manager refuses Steam's TDP: the slider writes nothing.
    vi.stubGlobal("settingsStore", { clientSettings: { ...settings, steamos_platform_performance_profile: "balanced" } });
    expect(readSteamTdpSlider()).toBe(false);
  });

  it("is off when Steam has never set it, and unknown without the store", () => {
    vi.stubGlobal("settingsStore", { clientSettings: {} });
    expect(readSteamTdpSlider()).toBe(false);

    vi.stubGlobal("settingsStore", undefined);
    expect(readSteamTdpSlider()).toBeNull();
  });
});
