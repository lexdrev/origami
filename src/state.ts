// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { backend, type Change, type Info, type Settings, type Telemetry } from "./backend";
import type { Language } from "./i18n";
import { readSteamLanguage } from "./steam";
import { createStore, errorMessage, type Loadable, type Store } from "./store";

export const info = createStore<Loadable<Info>>({ status: "loading" });
export const settings = createStore<Loadable<Settings>>({ status: "loading" });
export const changes = createStore<Loadable<Change[]>>({ status: "loading" });
export const telemetry = createStore<Loadable<Telemetry>>({ status: "loading" });
export const steamLanguage = createStore<Language>("en");
/** The last failed action, shown until the next one succeeds. */
export const actionError = createStore<string | null>(null);

async function load<T>(store: Store<Loadable<T>>, request: () => Promise<T>): Promise<void> {
  try {
    store.set({ status: "ready", value: await request() });
  } catch (error) {
    store.set({ status: "failed", error: errorMessage(error) });
  }
}

export async function loadAll(): Promise<void> {
  await Promise.all([
    load(info, backend.getInfo),
    load(settings, backend.getSettings),
    load(changes, backend.getChanges),
    readSteamLanguage().then(steamLanguage.set, (error: unknown) => {
      // English stays in place; the plugin still works.
      console.warn("ORIGAMI: cannot read the Steam language", error);
    }),
  ]);
}

export function refreshTelemetry(): Promise<void> {
  return load(telemetry, backend.getTelemetry);
}

export async function updateSettings(changes: Partial<Settings>): Promise<void> {
  try {
    settings.set({ status: "ready", value: await backend.updateSettings(changes) });
    actionError.set(null);
  } catch (error) {
    actionError.set(errorMessage(error));
  }
}
