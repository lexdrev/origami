// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { pluralForm } from "./format";
import type { Messages } from "./index";

const locale = "en-US";

export const en: Messages = {
  locale,
  unknown: "—",
  actions: { open: "Open", back: "Back", select: "Select", toggle: "Toggle" },
  units: { watts: "W", rpm: "rpm", celsius: "°C" },
  main: {
    settings: "Settings",
    tiles: { power: "Power", fans: "Fans", display: "Display & Light", gamepad: "Gamepad" },
    powerNow: (watts) => `now\u00a0${watts}`,
    boost: (on) => (on ? "boost\u00a0on" : "boost\u00a0off"),
    displaySub: "Saturation",
    gamepadSub: "Handle vibration",
  },
  settings: {
    title: "Settings",
    language: "Language",
    languages: { auto: "Same as Steam", ru: "Русский", en: "English" },
    system: "System",
    qamTab: "Quick access tab",
    qamTabOff: "Off · only inside Decky",
    qamTabFirst: "On · first in the column",
    qamTabLast: "On · last in the column",
    qamTabAbove: (tab) => `On · above ${tab}`,
    changes: "System changes",
    changesSummary: (count) =>
      count === 0
        ? "ORIGAMI has changed nothing"
        : `${count} ${pluralForm(locale, count, { one: "change", other: "changes" })} · restore all`,
    slogan: ["Every fold unfolds.", "Fold your handheld your way."],
  },
  qamTab: {
    title: "ORIGAMI tab",
    subtitle: "Settings · quick access menu",
    own: "Own tab",
    ownOn: "Fox in the quick access column",
    ownOff: "Only inside the Decky tab",
    place: "Place in the column",
    placeHint: "Move ORIGAMI up or down.",
    up: "Up",
    down: "Down",
    toTop: "To the top",
    toBottom: "To the bottom",
  },
  tabs: {
    notifications: "Notifications",
    remotePlay: "Remote Play Together",
    voiceChat: "Voice chat",
    friends: "Friends",
    quickSettings: "Quick settings",
    performance: "Performance",
    help: "Help",
    soundtracks: "Soundtracks",
    decky: "Decky",
    plugin: "Plugin",
  },
  changes: {
    title: "System changes",
    subtitle: "Settings · Every fold unfolds",
    system: "System",
    device: "Device",
    kernel: "Kernel",
    changed: (count) => (count === 0 ? "What ORIGAMI changed" : `What ORIGAMI changed · ${count}`),
    nothingChanged: "ORIGAMI has changed nothing",
    labels: {},
  },
  errors: { backend: "ORIGAMI backend did not respond" },
};
