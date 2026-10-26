// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { createContext, useContext, type ReactNode } from "react";

import type { ButtonAction, LanguageSetting, LightBrightness, LightMode, LightSpeed } from "../backend";
import type { PaletteColour } from "../lighting";
import type { VibrationPreset } from "../vibration";
import { en } from "./en";
import { ru } from "./ru";

export type Language = "ru" | "en";

/** An action as a choice: its name and what it does. */
export interface ActionText {
  name: string;
  detail: string;
}

export interface Messages {
  locale: string;
  unknown: string;
  /** The button under a section another plugin drives. */
  openDeckyPlugins: string;
  actions: { open: string; back: string; select: string; toggle: string; less: string; more: string };
  units: { watts: string; rpm: string; celsius: string };
  main: {
    settings: string;
    tiles: { power: string; fans: string; display: string; gamepad: string };
    powerNow(watts: string): string;
    boost(on: boolean): string;
    displaySub: string;
    gamepadSub: string;
  };
  settings: {
    title: string;
    language: string;
    languages: Record<LanguageSetting, string>;
    system: string;
    qamTab: string;
    qamTabOff: string;
    qamTabFirst: string;
    qamTabLast: string;
    /** Summary when another plugin, named or not, arranges the column. */
    qamTabArranged(plugin: string | null): string;
    qamTabAbove(tab: string): string;
    changes: string;
    changesSummary(count: number): string;
    slogan: readonly [string, string];
  };
  qamTab: {
    title: string;
    subtitle: string;
    own: string;
    ownOn: string;
    ownOff: string;
    place: string;
    placeHint: string;
    arranged(plugin: string | null): string;
    arrangedText: string;
    up: string;
    down: string;
    toTop: string;
    toBottom: string;
  };
  display: {
    title: string;
    saturation: string;
    saturationSub: string;
    presets: Record<"default" | "brighter" | "vivid" | "max" | "custom", string>;
    saturationOwnedBy(plugin: string): string;
    saturationOwnedText(plugin: string): string;
    lighting: string;
    lightingOn: string;
    lightingOff: string;
    mode: string;
    rings: { left: string; right: string };
    modes: Record<LightMode, string>;
    colour: string;
    colours: Record<PaletteColour["id"], string>;
    customColour: string;
    speed: string;
    speeds: Record<LightSpeed, string>;
    brightness: string;
    levels: Record<LightBrightness, string>;
    ownedBy(plugin: string): string;
    ownedText(plugin: string): string;
  };
  customColour: {
    title: string;
    subtitle: string;
    targets: { both: string; left: string; right: string };
    hue: string;
    saturation: string;
    white: string;
    pure: string;
    hint: string;
    cancel: string;
    apply: string;
  };
  gamepad: {
    title: string;
    vibration: string;
    /** Shown at full strength, which the controller has from the factory and after sleep. */
    tooStrong: string;
    handles: string;
    together: string;
    separate: string;
    left: string;
    right: string;
    test: string;
    presets: Record<VibrationPreset["id"], string>;
    vibrationOwnedBy(plugin: string): string;
    vibrationOwnedText(plugin: string): string;
    armouryCrate: string;
    armouryCrateUnassigned: string;
    qamAssist: string;
    /** The problem QAM assist solves, shown while it is off. */
    qamAssistOff: string;
    /** What QAM assist does, shown while it is on. */
    qamAssistOn: string;
  };
  armouryCrate: {
    title: string;
    subtitle: string;
    press: string;
    hold: string;
    actions: Record<Exclude<ButtonAction, "none">, ActionText>;
    /** A short press left alone: the button does nothing. */
    nothing: ActionText;
    /** Holding left alone: Steam gets the L5 it always gets. */
    l5: ActionText;
    /** Above the long-press choices: Steam gets L5 whatever ORIGAMI does. */
    holdHint: string;
    summary(press: string, hold: string): string;
  };
  /** Notifications of button actions, shown while the plugin is closed. */
  buttonActions: {
    closeGame: string;
    holdAgain(game: string): string;
    noGame: string;
  };
  /** Names of the quick access tabs, as Steam calls them. */
  tabs: {
    notifications: string;
    remotePlay: string;
    voiceChat: string;
    friends: string;
    quickSettings: string;
    performance: string;
    help: string;
    soundtracks: string;
    decky: string;
    plugin: string;
  };
  changes: {
    title: string;
    subtitle: string;
    system: string;
    device: string;
    kernel: string;
    changed(count: number): string;
    nothingChanged: string;
    /** Labels of journal entries by "module.key". */
    labels: Partial<Record<string, string>>;
  };
  errors: { backend: string };
}

const catalogs: Record<Language, Messages> = { en, ru };

const MessagesContext = createContext<Messages>(en);

export function I18nProvider({ language, children }: { language: Language; children: ReactNode }) {
  return <MessagesContext.Provider value={catalogs[language]}>{children}</MessagesContext.Provider>;
}

/** The messages of a language, for text shown outside React, such as notifications. */
export function messagesFor(language: Language): Messages {
  return catalogs[language];
}

export function useMessages(): Messages {
  return useContext(MessagesContext);
}

export function resolveLanguage(setting: LanguageSetting, steamLanguage: Language): Language {
  return setting === "auto" ? steamLanguage : setting;
}
