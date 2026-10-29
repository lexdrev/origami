// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import {
  backend,
  type Change,
  type Conflicts,
  type GyroState,
  type HeldPower,
  type Info,
  type Lighting,
  type Settings,
  type Telemetry,
  type TriggerState,
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
export const heldPower = createStore<Loadable<HeldPower>>({ status: "loading" });
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

/** The limits ORIGAMI holds follow the charger and other writers, so they are read with the telemetry. */
export function refreshHeldPower(): Promise<void> {
  return load(heldPower, backend.getPower);
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

/** What ORIGAMI changed follows every setting, so this is read when a screen showing it opens. */
export function refreshChanges(): Promise<void> {
  return load(changes, backend.getChanges);
}

/** Loads again what failed to load: the backend may have started late. Runs as the plugin opens. */
export async function reloadFailed(): Promise<void> {
  await Promise.all([
    info.get().status === "failed" && load(info, backend.getInfo),
    settings.get().status === "failed" && load(settings, backend.getSettings),
    changes.get().status === "failed" && load(changes, backend.getChanges),
  ]);
}

function reloadSettings(): Promise<void> {
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

/** Gives the system back as it was before ORIGAMI and unsets its fixes; the plugin stays. */
export function restoreAll(): Promise<boolean> {
  return act(async () => {
    settings.set({ status: "ready", value: await backend.restoreAll() });
    await Promise.all([refreshChanges(), refreshGyro(), refreshHeldPower()]);
  });
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

/**
 * A setting shown at once and saved in the background, so a slider follows a held D-pad. Quick
 * changes save only the newest value, and the backend's answer is shown only while no newer value
 * waits: an answer for a value the user has left would move the slider back. A refused value brings
 * the saved settings back.
 */
function liveSetting<K extends keyof Settings>(key: K, after?: () => Promise<void>) {
  const saver = latestOnly(async (value: Settings[K]) => {
    try {
      const saved = await backend.updateSettings({ [key]: value });
      actionError.set(null);
      if (!saver.waiting()) settings.set({ status: "ready", value: saved });
    } catch (error) {
      actionError.set(errorMessage(error));
      if (!saver.waiting()) await reloadSettings();
    }
    await after?.();
  });
  return (value: Settings[K]): void => {
    const current = settings.get();
    if (current.status !== "ready") return;
    settings.set({ status: "ready", value: { ...current.value, [key]: value } });
    saver.send(value);
  };
}

/** Saves the vibration strength. */
export const setVibration = liveSetting("vibration");
/** Saves the trigger rumble. */
export const setTriggerRumble = liveSetting("triggerRumble");
/** Saves the power settings; the limits ORIGAMI holds follow them. */
export const setPower = liveSetting("power", refreshHeldPower);
/** Saves the fan curve. */
export const setFans = liveSetting("fans");
/** Saves the games' own power settings; the limits held follow them too. */
export const setGamePower = liveSetting("gamePower", refreshHeldPower);

/** Switches the stick lighting on or off; it comes on as ORIGAMI's default the first time. */
export function toggleLighting(): Promise<boolean> {
  const current = settings.get();
  if (current.status !== "ready") {
    // Pressed before the settings loaded: the error says so, not whatever failed before.
    actionError.set(currentMessages().errors.backend);
    return Promise.resolve(false);
  }
  const lighting = current.value.lighting;
  return updateSettings({ lighting: { ...(lighting ?? DEFAULT_LIGHTING), enabled: !(lighting?.enabled ?? false) } });
}
