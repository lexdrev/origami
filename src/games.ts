// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { Router } from "@decky/ui";

import { backend } from "./backend";
import type { Game } from "./gameProfiles";
import { createStore } from "./store";

// Steam shows the game it runs as MainRunningApp some seconds before its lifetime notification
// (HARDWARE.md), so the game's own power follows MainRunningApp.

const LOOK_MS = 1000;

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
