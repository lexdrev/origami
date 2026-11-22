// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { createContext, useContext, type ReactNode } from "react";

import type {
  ButtonAction,
  CleanupKind,
  LanguageSetting,
  LightMode,
  LightSpeed,
  SoundVolume,
  SoundWidth,
  TriggerLevel,
  Triggers,
} from "../backend";
import type { FanPreset, HoldState } from "../fans";
import type { LightLevel, PaletteColour } from "../lighting";
import type { TriggerPattern } from "../triggers";
import type { TdpPreset } from "../power";
import type { SaturationPreset } from "../saturation";
import type { SharpnessPreset, SharpnessStatus } from "../sharpness";
import type { VibrationPreset } from "../vibration";
import { de } from "./de";
import { en } from "./en";
import { es } from "./es";
import { fr } from "./fr";
import { ru } from "./ru";
import { zh } from "./zh";

export type Language = "de" | "en" | "es" | "fr" | "ru" | "zh";

/** The languages by their own names: a list of them is read by those who know none of the others. */
export const LANGUAGE_NAMES: Record<Language, string> = {
  de: "Deutsch",
  en: "English",
  es: "Español",
  fr: "Français",
  ru: "Русский",
  zh: "简体中文",
};
/** The languages in the order of the list to choose from: by their names, each alphabet in turn. */
export const LANGUAGES: readonly Language[] = ["de", "en", "es", "fr", "ru", "zh"];

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
  actions: {
    open: string;
    back: string;
    select: string;
    toggle: string;
    less: string;
    more: string;
    check: string;
    update: string;
  };
  units: { watts: string; rpm: string; celsius: string; mb: string; gb: string };
  main: {
    settings: string;
    tiles: { power: string; fans: string; display: string; gamepad: string; sound: string; service: string };
    powerNow(watts: string): string;
    boost(on: boolean): string;
    displaySub: string;
    lighting(on: boolean): string;
    gamepadSub: string;
    triggers: { off: string; steady: string; taps: string };
    /** The fan curve on the Fans tile. */
    curve(name: string): string;
    /** The temperature the fans hold, in its place. */
    target(temp: string): string;
    /** Under the system in the header, once the daily check has found a newer release. */
    updateAvailable(version: string): string;
    /** The Sound tile while the filter is off, and under it. */
    soundOff: string;
    soundOffSub: string;
    /** Under the Sound tile while another plugin, or a program outside Decky, processes the speakers. */
    soundOther: string;
    soundOtherProgram: string;
    /** The Sound tile while headphones play, and under it. */
    soundPaused: string;
    soundHeadphones: string;
    /** Under the Sound tile while the filter is on and not at work. */
    soundFailed: string;
    soundNoSpeakers: string;
    soundWidths: Record<SoundWidth, string>;
    soundVoices: string;
    /** Under the Service tile; its value while the sharpness is off, and while another plugin sets it. */
    sharpnessSub: string;
    sharpnessOff: string;
    sharpnessOther: string;
    /** Under the Service tile while the running game's launch options keep the sharpness. */
    sharpnessLaunch: string;
    /** Under the Service tile where it has no sharpness: its value is the space left on the disk. */
    storageSub: string;
    /** After the sharpness under the Service tile: the space left on the disk. */
    storageFree(size: string): string;
  };
  settings: {
    title: string;
    language: string;
    /** Under the Language screen's title. */
    languageSubtitle: string;
    /** The choice that follows Steam's own language. */
    likeSteam: string;
    /** Under that choice: the language it gives now, by its own name. */
    likeSteamNow(language: string): string;
    system: string;
    manageTdp: string;
    /** What ORIGAMI does while it manages the TDP. */
    manageTdpOn: string;
    /** The problem left while it does not: Steam sets the TDP, and it drops. */
    manageTdpOff: string;
    /** When to switch it off. */
    manageTdpNote: string;
    /** When to switch it on again. */
    manageTdpOffNote: string;
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
    /** The updates card: the check, the update on offer, the releases on GitHub and the daily check. */
    updates: {
      title: string;
      /** Before the first check: the version that runs, and that a press asks GitHub. */
      idle(version: string): string;
      checking(version: string): string;
      latest(version: string): string;
      available(version: string): string;
      failed: string;
      refused: string;
      check: string;
      /** The check button while GitHub has not answered yet. */
      busy: string;
      update: string;
      whatsNew: string;
      /** Under an offered update: Decky asks first, and a running game is better closed. */
      confirm: string;
      /** When Decky did not take the update: the zip is on the releases page. */
      download: string;
      daily: string;
      dailyOn: string;
      dailyOff: string;
    };
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
    /** The arranging plugin is switched off, but its render stays until Steam restarts. */
    arrangedUntilRestart(plugin: string): string;
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
    until(percent: number): string;
    drain: string;
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
    /** In place of the boost switch while another plugin holds the boost alone, as Ally Fix does. */
    boostOwnedBy(plugin: string): string;
    boostOwnedText(plugin: string): string;
    /** Under the TDP on the dial while a game's own settings are shown. */
    gameLimit: string;
    /** The switch of the running game's own profile, like Steam's per-game profile. */
    gameProfile: string;
    /** Under the switch: the game, and whose settings the screen sets now. */
    gameProfileOn(game: string): string;
    gameProfileOff(game: string): string;
    /** A grey line while the switch is off and the game's profile is kept. */
    gameProfileKept: string;
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
    /** The card's head while the fans hold a temperature. */
    holds(temp: string): string;
    /** Under the curve's name while it is on: what the preset gives and what it costs. */
    curveSubs: Record<FanPreset["id"] | "custom", string>;
    /** Under the target while it is held: how the fans stand to it. */
    holdSubs: Record<Exclude<HoldState, "under">, string>;
    /** In its place while a temperature under the firmware's floor is held instead of the target. */
    holdUnder(held: string, floor: string): string;
    curveOff: string;
    presets: Record<FanPreset["id"] | "default" | "custom", string>;
    speedNow(temp: string, speed: string): string;
    /** The same while the firmware's own floor runs the fans faster than the curve asks. */
    speedNowFirmware(temp: string, speed: string): string;
    chart: string;
    preset: string;
    point: string;
    speedAt(temp: string): string;
    safety: string;
    mode: string;
    modes: { curve: string; hold: string };
    target: string;
    holdNote: string;
    /** In place of the note while the fans run at full speed and the chip is warmer than asked. */
    holdFull: string;
    /** Under the settings where the firmware has a floor: from where, how fast, and until when. */
    floorNote(from: string, speed: string, back: string): string;
    ownedBy(plugin: string): string;
    ownedText(plugin: string): string;
  };
  sound: {
    title: string;
    card: string;
    on: string;
    off: string;
    /** While headphones play on the speakers' sink. */
    headphones: string;
    /** While PipeWire has no speaker sink. */
    noSpeakers: string;
    /** Under the alert while a program outside Decky's plugins processes the speakers. */
    filterOwnedText(program: string): string;
    /** The switch of the running game's own sound, and the list of such games. */
    gameSound: string;
    profilesTitleSub: string;
    profilesHint: string;
    /** While the filter comes up, and when it did not. */
    starting: string;
    failed: string;
    volume: string;
    volumeNote: string;
    volumes: Record<SoundVolume, string>;
    width: string;
    widthNote: string;
    widths: Record<SoundWidth, string>;
    voices: string;
    voicesSub: string;
    ownedBy(plugin: string): string;
    ownedText(plugin: string): string;
    clockFix: string;
    clockFixOn: string;
    clockFixOff: string;
    clockFixWhy: string;
  };
  service: {
    title: string;
    sharpness: string;
    /** Under the card's title: by its switch, and by the running game. */
    status: Record<SharpnessStatus, string>;
    /** What the sharpening is, and when a game takes it. */
    sharpnessNote: string;
    launchNote: string;
    strength: string;
    strengthNote: string;
    presets: Record<SharpnessPreset["id"] | "custom", string>;
    /** The switch of the running game's own sharpness, and the list of such games. */
    gameSharpness: string;
    profiles: string;
    profilesSub: string;
    profilesTitleSub: string;
    profilesHint: string;
    /** A game's sharpness in a line of the list. */
    summary(strength: number): string;
    ownedBy(plugin: string): string;
    ownedText(plugin: string): string;
    /** In a game started through a plugin's own wrapper: whose the sharpness is, and why. */
    launcherOwnedBy(plugin: string): string;
    launcherText(game: string): string;
    /** Where that plugin has its own sharpening, by the key the backend names; else the plain sentence. */
    launcherSharpening: Partial<Record<string, string>>;
    launcherOwn: string;
    /** How to have ORIGAMI's sharpness in that game, and the frame generation it works with. */
    launcherAdvice(companion: string): string;
    /** In a game whose launch options set the sharpening layer by themselves. */
    launchOwned: string;
    launchText(game: string): string;
    /** Under that: a frame generation plugin in whose games ORIGAMI's sharpness does work. */
    companionText(plugin: string): string;
    /** The row that opens the Cleanup screen. */
    cleanup: string;
    cleanupSub: string;
  };
  cleanup: {
    title: string;
    subtitle: string;
    scanning: string;
    storage(free: string, total: string): string;
    /** While a game runs nothing is listed. */
    gameRuns: string;
    gameRunsText: string;
    /** What removed games left behind: the list's name, what it holds, and the note inside. */
    leftovers: string;
    leftoversSub: string;
    leftoversHint: string;
    noLeftovers: string;
    /** A Steam library is not mounted, so what is removed cannot be told. */
    incomplete: string;
    incompleteText: string;
    /** The shader caches of the installed games. */
    caches: string;
    cachesSub: string;
    cachesHint: string;
    noCaches: string;
    /** Under a folded list: how much is picked in it. */
    picked(count: number, size: string): string;
    kinds: Record<CleanupKind, string>;
    underOneMb: string;
    /** A game Steam cannot name, and a non-Steam game whose shortcut is gone. */
    unknownGame(appId: number): string;
    removedShortcut(appId: number): string;
    /** Under a prefix: where the game's saves are. */
    cloud: string;
    noCloud: string;
    cloudUnknown: string;
    shortcutNote: string;
    folderNote: string;
    /** Folders a game nothing names made in its prefix. */
    inside(names: string): string;
    busy: string;
    pickSafe: string;
    /** The button with nothing picked, and with something. */
    pickFirst: string;
    remove(size: string): string;
    ask: string;
    askText(count: number, size: string): string;
    /** How many of the picked hold saves that are nowhere else. */
    askSaves(count: number): string;
    confirm: string;
    freed(size: string): string;
    failed: string;
  };
  display: {
    title: string;
    saturation: string;
    saturationSub: string;
    /** On SteamOS, after the subtitle: the system shows the most already. */
    saturationSteamOs: string;
    presets: Record<SaturationPreset["id"] | "custom", string>;
    saturationOwnedBy(plugin: string): string;
    saturationOwnedText(plugin: string): string;
    lighting: string;
    lightingOn: string;
    lightingOff: string;
    /** Never set: the controller keeps its own lighting. */
    lightingUnset: string;
    mode: string;
    rings: { left: string; right: string };
    modes: Record<LightMode, string>;
    colour: string;
    colours: Record<PaletteColour["id"], string>;
    customColour: string;
    speed: string;
    speeds: Record<LightSpeed, string>;
    brightness: string;
    /** Over the slider of rainbow and spiral, which only the controller's three levels dim. */
    brightnessSteps: string;
    levels: Record<LightLevel, string>;
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
    /** Never set: the controller's own strength, without ORIGAMI's lift. */
    vibrationUnset: string;
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
    /** The fix of the system's overlay menu, the problem while it is off, what it does while on. */
    overlayFix: string;
    overlayFixOff: string;
    overlayFixOn: string;
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
  errors: {
    backend: string;
    /** The backend cannot run on this Decky Loader: what is needed and what the console has. */
    notStarted: string;
    oldDecky: (version: string) => string;
    /** The backend has not answered for a while for some other reason. */
    notResponding: string;
    restart: string;
  };
}

const catalogs: Record<Language, Messages> = { de, en, es, fr, ru, zh };

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
