// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import type { Language } from "./i18n";

/** Interface language of the Steam client, reduced to the languages ORIGAMI has. */
export async function readSteamLanguage(): Promise<Language> {
  const language = await window.SteamClient.Settings.GetCurrentLanguage();
  return language === "russian" ? "ru" : "en";
}
