// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import type { Language } from "./i18n";

// Steam's client settings, which its settings store keeps in clientSettings: on SteamOS systems
// (steamos-manager) the quick access TDP slider is the client setting steamos_tdp_limit, switched
// by steamos_tdp_limit_enabled, one for all games. steamos-manager takes Steam's TDP only in the
// performance profile (steamos_platform_performance_profile), so in another the slider sets
// nothing. The performance store's own TDP limit is the Steam Deck's and stays unchanged here
// (read from the Steam client on 2026-10-28).

interface ClientSettings {
  steamos_tdp_limit_enabled?: boolean;
  steamos_tdp_limit?: number;
  steamos_platform_performance_profile?: string;
}

/** The profile in which steamos-manager takes Steam's TDP. */
const TDP_PROFILE = "performance";

function clientSettings(): ClientSettings | null {
  // Steam's window is the global object; tests stand in for it there.
  const store: unknown = (globalThis as { settingsStore?: unknown }).settingsStore;
  if (typeof store !== "object" || store === null || !("clientSettings" in store)) return null;
  const settings = store.clientSettings;
  return typeof settings === "object" && settings !== null ? settings : null;
}

/** Steam's own TDP limit: whether its slider sets the TDP now, and its watts. */
export interface SteamTdpLimit {
  /** The slider is on and the profile lets Steam write the TDP. */
  enabled: boolean;
  watts: number | null;
}

/** Null where Steam has no client settings ORIGAMI knows. */
export function readSteamTdpLimit(): SteamTdpLimit | null {
  const settings = clientSettings();
  if (settings === null) return null;
  return {
    enabled: settings.steamos_tdp_limit_enabled === true && settings.steamos_platform_performance_profile === TDP_PROFILE,
    watts: settings.steamos_tdp_limit ?? null,
  };
}

/** Interface language of the Steam client, reduced to the languages ORIGAMI has. */
export async function readSteamLanguage(): Promise<Language> {
  const language = await window.SteamClient.Settings.GetCurrentLanguage();
  return language === "russian" ? "ru" : "en";
}
