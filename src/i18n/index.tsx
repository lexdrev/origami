// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { createContext, useContext, type ReactNode } from "react";

import type {
  ButtonAction,
  LanguageSetting,
  LightBrightness,
  LightMode,
  LightSpeed,
  TriggerLevel,
  Triggers,
} from "../backend";
import type { FanPreset } from "../fans";
import type { PaletteColour } from "../lighting";
import type { TriggerPattern } from "../triggers";
import type { TdpPreset } from "../power";
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
    lighting(on: boolean): string;
    gamepadSub: string;
    triggers: { off: string; steady: string; taps: string };
    /** The fan curve on the Fans tile. */
    curve(name: string): string;
  };
  settings: {
    title: string;
    language: string;
    languages: Record<LanguageSetting, string>;
    system: string;
    manageTdp: string;
    /** What ORIGAMI does while it manages the TDP. */
    manageTdpOn: string;
    /** The problem left while it does not: Steam sets the TDP, and it drops. */
    manageTdpOff: string;
    /** When to switch it off. */
    manageTdpNote: string;
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
    /** The action of the About block: the project's page in Steam's browser. */
    openProject: string;
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
  power: {
    title: string;
    /** Under the TDP on the dial. */
    limit: string;
    /** The power drawn now: on the dial where ORIGAMI does not set the TDP, under it where it does. */
    now: string;
    /** The SoC draws far less than the limit: nothing runs that needs it. */
    noLoad: string;
    /** On the dial while Steam's TDP slider is on: ORIGAMI writes over it. */
    steamSliderIdle: string;
    tdp: string;
    tdpSub: string;
    presets: Record<TdpPreset["id"] | "custom", string>;
    headroom: string;
    headroomOn: string;
    headroomOff: string;
    limits: { spl: string; sppt: string; fppt: string };
    cpuBoost: string;
    cpuBoostOn: string;
    cpuBoostOff: string;
    batteryHigh: string;
    batteryHighOn: string;
    batteryHighOff: string;
    battery: string;
    charging: string;
    timeLeft(hours: number, minutes: number): string;
    capacity: string;
    steamSlider: string;
    steamSliderText: string;
    openPerformance: string;
    contested: string;
    contestedText: string;
    steamSets: string;
    steamSetsText: string;
    ownedBy(plugin: string): string;
    ownedText(plugin: string): string;
    /** Under the TDP on the dial while a game's own settings are shown. */
    gameLimit: string;
    /** The strip of a game: its own settings or the general ones. */
    profile: string;
    general: string;
    /** Under the strip: what the screen sets now. */
    gameOnly: string;
    chooseGame: string;
    profileWaits: string;
    /** Beside a setting a game sets otherwise, with the general value where it is short. */
    differs(general?: string): string;
    profiles: string;
    /** Under the row of game profiles while no game runs. */
    profilesSub: string;
    /** Under the title of the list of game profiles. */
    profilesTitleSub: string;
    profilesHint: string;
    /** Under a game's name when its profile is opened from the list and the game is not running. */
    profileSub: string;
    /** The headroom in a profile's summary, by its other name. */
    tdpBoost(on: boolean): string;
    profileWaiting: string;
    removeProfile: string;
    removeAgain: string;
  };
  fans: {
    title: string;
    fans: readonly [string, string];
    parts: readonly [string, string];
    minuteAgo: string;
    now: string;
    history(fan: string): string;
    temperatures: readonly [string, string];
    curve(name: string): string;
    /** Under the curve's name while it is on: what the preset gives and what it costs. */
    curveSubs: Record<FanPreset["id"] | "custom", string>;
    curveOff: string;
    presets: Record<FanPreset["id"] | "default" | "custom", string>;
    speedNow(temp: string, speed: string): string;
    chart: string;
    preset: string;
    point: string;
    speedAt(temp: string): string;
    safety: string;
    ownedBy(plugin: string): string;
    ownedText(plugin: string): string;
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
    off: string;
    /** While the handle vibration is on. */
    vibrationOn: string;
    /** While it is off: games rumble the handles no more. */
    vibrationStill: string;
    strength: string;
    handles: string;
    together: string;
    separate: string;
    left: string;
    right: string;
    test: string;
    presets: Record<VibrationPreset["id"] | "custom", string>;
    vibrationOwnedBy(plugin: string): string;
    vibrationOwnedText(plugin: string): string;
    triggers: string;
    /** While the triggers are off: InputPlumber sends their motors nothing. */
    triggersStill: string;
    /** What the trigger rumble follows while it is on. */
    triggersOn: string;
    triggerChoices: Record<Triggers, string>;
    /** Labels over the trigger card's strips, as over the stick lighting's. */
    triggerSides: string;
    triggerCharacter: string;
    triggerPattern: string;
    /** Steady rumble follows a game's whole rumble; taps give one short tap on each shot. */
    triggerPatterns: Record<TriggerPattern, string>;
    triggerStrength: string;
    triggerLevels: Record<TriggerLevel, string>;
    /** Under the levels: what their percentages mean. */
    triggerStrengthNote: string;
    triggersOwnedBy(plugin: string): string;
    triggersOwnedText(plugin: string): string;
    armouryCrate: string;
    armouryCrateUnassigned: string;
    qamAssist: string;
    /** The problem QAM assist solves, shown while it is off. */
    qamAssistOff: string;
    /** What QAM assist does, shown while it is on. */
    qamAssistOn: string;
    gyroFix: string;
    /** Under the switch while the fix is on: Steam's own fix in each layout would turn it back. */
    gyroFixOn: string;
    /** The problem the fix solves, shown while it is off. */
    gyroFixOff: string;
    /** InputPlumber restarts to take the axes; the controller is away for a few seconds. */
    gyroFixRestart: string;
    gyroForeign: string;
    gyroForeignText: string;
  };
  armouryCrate: {
    title: string;
    subtitle: string;
    press: string;
    hold: string;
    actions: Record<Exclude<ButtonAction, "none" | "l5">, ActionText>;
    /** A short press left alone: the button does nothing. */
    nothing: ActionText;
    /** Holding left alone: Steam gets the L5 it always gets; a short press can give it too. */
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
    /** After "restore everything": the journal is empty, and the fixes are off. */
    restored: string;
    /** Labels of journal entries by "module.key". */
    labels: Partial<Record<string, string>>;
    restore: string;
    /** The question in place of the button, with what it does and what it brings back. */
    restoreAsk: string;
    restoreText: string;
    restoreNote: string;
    cancel: string;
    confirm: string;
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
