// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { createContext, useContext, type ReactNode } from "react";

import type { LanguageSetting } from "../backend";
import { en } from "./en";
import { ru } from "./ru";

export type Language = "ru" | "en";

export interface Messages {
  locale: string;
  unknown: string;
  actions: { open: string; back: string; select: string; toggle: string };
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
  gamepad: {
    title: string;
    qamAssist: string;
    /** The problem QAM assist solves, shown while it is off. */
    qamAssistOff: string;
    qamAssistOn(rescued: number): string;
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

export function useMessages(): Messages {
  return useContext(MessagesContext);
}

export function resolveLanguage(setting: LanguageSetting, steamLanguage: Language): Language {
  return setting === "auto" ? steamLanguage : setting;
}
