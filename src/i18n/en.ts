// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { pluralForm } from "./format";
import type { Messages } from "./index";

const locale = "en-US";

export const en: Messages = {
  locale,
  unknown: "—",
  actions: { open: "Open", back: "Back", select: "Select" },
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
    changes: "System changes",
    changesSummary: (count) =>
      count === 0
        ? "ORIGAMI has changed nothing"
        : `${count} ${pluralForm(locale, count, { one: "change", other: "changes" })} · restore all`,
    slogan: ["Every fold unfolds.", "Fold your handheld your way."],
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
