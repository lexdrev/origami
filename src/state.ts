// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import {
  backend,
  type Change,
  type Conflicts,
  type GyroState,
  type Info,
  type Lighting,
  type Settings,
  type Telemetry,
  type TriggerRumble,
  type TriggerState,
  type Vibration,
} from "./backend";
import { messagesFor, resolveLanguage, type Language, type Messages } from "./i18n";
import { DEFAULT_LIGHTING } from "./lighting";
import { readSteamLanguage } from "./steam";
import { createStore, errorMessage, latestOnly, useStore, type Loadable, type Store } from "./store";

export const info = createStore<Loadable<Info>>({ status: "loading" });
export const settings = createStore<Loadable<Settings>>({ status: "loading" });
export const changes = createStore<Loadable<Change[]>>({ status: "loading" });
export const telemetry = createStore<Loadable<Telemetry>>({ status: "loading" });
export const conflicts = createStore<Loadable<Conflicts>>({ status: "loading" });
export const gyro = createStore<Loadable<GyroState>>({ status: "loading" });
export const triggerState = createStore<Loadable<TriggerState>>({ status: "loading" });
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

function languageOf(current: Loadable<Settings>, steam: Language): Language {
  return resolveLanguage(current.status === "ready" ? current.value.language : "auto", steam);
}

/** Interface language: the setting, or the Steam language when the setting is "auto". */
export function useLanguage(): Language {
  return languageOf(useStore(settings), useStore(steamLanguage));
}

/** The interface messages outside React, such as for notifications. */
export function currentMessages(): Messages {
  return messagesFor(languageOf(settings.get(), steamLanguage.get()));
}

export function refreshTelemetry(): Promise<void> {
  return load(telemetry, backend.getTelemetry);
}

/** InputPlumber's device files change with updates and other programs, so this is read when the screen opens. */
export function refreshGyro(): Promise<void> {
  return load(gyro, backend.getGyro);
}

/** The controller can be missing for a moment, so this is read when the screen opens. */
export function refreshTriggerState(): Promise<void> {
  return load(triggerState, backend.getTriggerState);
}

/** Other plugins can be switched on and off at any time, so this is read when a screen opens. */
export function refreshConflicts(): Promise<void> {
  return load(conflicts, backend.getConflicts);
}

export function reloadSettings(): Promise<void> {
  return load(settings, backend.getSettings);
}

/** Runs a user's action; a failure shows until the next action succeeds. False when it failed. */
async function act(action: () => Promise<unknown>): Promise<boolean> {
  try {
    await action();
    actionError.set(null);
    return true;
  } catch (error) {
    actionError.set(errorMessage(error));
    return false;
  }
}

/** Shows lighting on the rings without saving it. */
export function previewLighting(lighting: Lighting): Promise<boolean> {
  return act(() => backend.previewLighting(lighting));
}

/** Rumbles the handles for a moment at the current strength. */
export function testVibration(): Promise<boolean> {
  return act(backend.testVibration);
}

/** Rumbles the chosen triggers for a moment, as a game's full rumble would. */
export function testTriggerRumble(): Promise<boolean> {
  return act(backend.testTriggerRumble);
}

/** Saves settings changes; the backend keeps only what the hardware took. */
export function updateSettings(changes: Partial<Settings>): Promise<boolean> {
  return act(async () => {
    settings.set({ status: "ready", value: await backend.updateSettings(changes) });
  });
}

// A slider moved quickly saves only its newest strength; a refused one brings the saved settings back.
const saveVibration = latestOnly(async (vibration: Vibration) => {
  if (!(await updateSettings({ vibration }))) await reloadSettings();
});

/** Saves the vibration strength, shown at once so the slider follows a held D-pad. */
export function setVibration(vibration: Vibration): void {
  const current = settings.get();
  if (current.status !== "ready") return;
  settings.set({ status: "ready", value: { ...current.value, vibration } });
  saveVibration.send(vibration);
}

const saveTriggerRumble = latestOnly(async (triggerRumble: TriggerRumble) => {
  if (!(await updateSettings({ triggerRumble }))) await reloadSettings();
});

/** Saves the trigger rumble, shown at once like the vibration strength. */
export function setTriggerRumble(triggerRumble: TriggerRumble): void {
  const current = settings.get();
  if (current.status !== "ready") return;
  settings.set({ status: "ready", value: { ...current.value, triggerRumble } });
  saveTriggerRumble.send(triggerRumble);
}

/** Switches the stick lighting on or off; it comes on as ORIGAMI's default the first time. */
export function toggleLighting(): Promise<boolean> {
  const current = settings.get();
  if (current.status !== "ready") return Promise.resolve(false);
  const lighting = current.value.lighting;
  return updateSettings({ lighting: { ...(lighting ?? DEFAULT_LIGHTING), enabled: !(lighting?.enabled ?? false) } });
}
