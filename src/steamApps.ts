// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import type { Cloud } from "./cleanup";

// What Steam's own interface knows of a game by its app id, installed or not.

type AppDetails = Parameters<Parameters<typeof window.SteamClient.Apps.RegisterForAppDetails>[1]>[0];

/** The game's name as the library shows it; null for a game Steam does not know. */
export function steamName(appId: number): string | null {
  const name = window.appStore.GetAppOverviewByAppID(appId)?.display_name;
  return name === undefined || name === "" ? null : name;
}

/** The game's details as Steam has them now; null when Steam does not answer in time. */
export function appDetails(appId: number, waitMs: number): Promise<AppDetails | null> {
  return new Promise((resolve) => {
    const asked: { answered?: true; registration?: { unregister: () => void } } = {};
    const answer = (details: AppDetails | null) => {
      if (asked.answered) return;
      asked.answered = true;
      clearTimeout(timer);
      asked.registration?.unregister();
      resolve(details);
    };
    const timer = setTimeout(() => {
      answer(null);
    }, waitMs);
    const registration = window.SteamClient.Apps.RegisterForAppDetails(appId, answer);
    // Steam may answer before the registration is returned.
    if (asked.answered) registration.unregister();
    else asked.registration = registration;
  });
}

/** How long Steam may take to tell of a game's cloud; it answers at once for a game it knows. */
const CLOUD_WAIT_MS = 1000;

/** Whether Steam keeps the game's saves in its cloud, for this game and this account. */
export async function cloudSaves(appId: number): Promise<Cloud> {
  const details = await appDetails(appId, CLOUD_WAIT_MS);
  if (details === null) return "unknown";
  return details.bCloudAvailable && details.bCloudEnabledForApp && details.bCloudEnabledForAccount ? "cloud" : "local";
}
