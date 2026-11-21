// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { Router } from "@decky/ui";

import { backend } from "./backend";
import type { Game } from "./gameProfiles";
import { createStore } from "./store";

// Steam shows the game it runs as MainRunningApp some seconds before its lifetime notification
// (HARDWARE.md), so the game's own power follows MainRunningApp.

const LOOK_MS = 1000;

/** What Steam calls starting a game, among the actions it tells of. */
const LAUNCH = "LaunchApp";

/** The game Steam runs now; null while none runs. */
export const runningGame = createStore<Game | null>(null);

/** The game whose profile is open from the list of profiles. */
export const openedProfile = createStore<Game | null>(null);

function readRunningGame(): Game | null {
  const app = Router.MainRunningApp;
  if (app === undefined) return null;
  const appId = app.appid;
  return Number.isSafeInteger(appId) && appId > 0 ? { appId, name: app.display_name } : null;
}

/** Starts telling the backend which game runs, so its own power applies. Returns the function that stops it. */
export function watchRunningGame(): () => void {
  let reported: number | null | undefined;
  let sending = false;
  const look = () => {
    const game = readRunningGame();
    const shown = runningGame.get();
    if (game?.appId !== shown?.appId || game?.name !== shown?.name) runningGame.set(game);
    const appId = game?.appId ?? null;
    if (appId === reported || sending) return;
    sending = true;
    backend
      .setGame(appId)
      .then(() => {
        reported = appId;
      })
      .catch((error: unknown) => {
        console.warn("ORIGAMI: cannot tell the backend which game runs", error);
      })
      .finally(() => {
        sending = false;
      });
  };
  look();
  const timer = setInterval(look, LOOK_MS);
  return () => {
    clearInterval(timer);
  };
}

/** How long Steam may take to answer with a game's details; it answers at once. */
const DETAILS_WAIT_MS = 300;

/** The game's launch options as Steam has them now; null when Steam does not answer in time. */
export function launchOptions(appId: number): Promise<string | null> {
  return new Promise((resolve) => {
    const asked: { answered?: true; registration?: { unregister: () => void } } = {};
    const answer = (options: string | null) => {
      if (asked.answered) return;
      asked.answered = true;
      clearTimeout(timer);
      asked.registration?.unregister();
      resolve(options);
    };
    const timer = setTimeout(() => {
      answer(null);
    }, DETAILS_WAIT_MS);
    const registration = window.SteamClient.Apps.RegisterForAppDetails(appId, (details) => {
      answer(details.strLaunchOptions);
    });
    // Steam may answer before the registration is returned.
    if (asked.answered) registration.unregister();
    else asked.registration = registration;
  });
}

/**
 * Starts telling the backend of every game Steam launches, before the game's process is there:
 * the sharpness is ready by the time the game loads its Vulkan layers. Returns the function that
 * stops it.
 */
export function watchGameLaunches(): () => void {
  const registration = window.SteamClient.Apps.RegisterForGameActionStart((_actionId, appId, action) => {
    const id = Number(appId);
    if (action !== LAUNCH || !Number.isSafeInteger(id) || id <= 0) return;
    // Launch options that set the sharpening layer themselves keep it, so the backend reads them.
    launchOptions(id)
      .then((options) => backend.gameStarting(id, options))
      .catch((error: unknown) => {
        console.warn("ORIGAMI: cannot tell the backend that a game is launched", error);
      });
  });
  return () => {
    registration.unregister();
  };
}
