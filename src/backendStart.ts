// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { callLoader } from "./deckyLoader";
import { settings } from "./state";
import { createStore } from "./store";

// Decky Loader runs the backend with the Python it is built with: 3.11 up to Decky 3.2.10, 3.14 from
// 3.3.0. The backend needs 3.14 and does not start on older Decky, so the screens would stay empty.
const FIRST_DECKY = { major: 3, minor: 3 };
/** How long the screens wait for the backend's first answer before saying it is missing. */
export const BACKEND_WAIT_MS = 10_000;

export type MissingBackend = { reason: "oldDecky"; deckyVersion: string } | { reason: "silent" };

/** Why the backend has not answered, once that is known. */
export const missingBackend = createStore<MissingBackend | null>(null);

/** Whether a Decky Loader version, such as "v3.2.10", is too old for the backend. Unreadable ones ("dev") pass. */
export function isOldDecky(version: string): boolean {
  const match = /^v?(\d+)\.(\d+)\./.exec(version);
  if (match === null) return false;
  const major = Number(match[1]);
  const minor = Number(match[2]);
  return major < FIRST_DECKY.major || (major === FIRST_DECKY.major && minor < FIRST_DECKY.minor);
}

/** Decky's own version, as its settings page reads it; null when Decky cannot tell. */
async function readDeckyVersion(): Promise<string | null> {
  try {
    return (await callLoader<{ current: string }>("updater/get_version_info")).current;
  } catch (error) {
    console.warn("ORIGAMI: cannot read the Decky Loader version", error);
    return null;
  }
}

/**
 * Finds out why the screens may stay empty: a Decky too old for the backend is known at once, any
 * other silence after BACKEND_WAIT_MS. Stopping it cancels the wait.
 */
export function watchBackendStart(): () => void {
  void readDeckyVersion().then((version) => {
    if (version !== null && isOldDecky(version) && settings.get().status !== "ready") {
      missingBackend.set({ reason: "oldDecky", deckyVersion: version.replace(/^v/, "") });
    }
  });
  const timer = setTimeout(() => {
    if (settings.get().status === "loading" && missingBackend.get() === null) missingBackend.set({ reason: "silent" });
  }, BACKEND_WAIT_MS);
  return () => {
    clearTimeout(timer);
  };
}
