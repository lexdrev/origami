// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { pluralForm } from "./format";
import type { Messages } from "./index";

const locale = "ru-RU";

export const ru: Messages = {
  locale,
  unknown: "—",
  actions: { open: "Открыть", back: "Назад", select: "Выбрать" },
  units: { watts: "Вт", rpm: "об/мин", celsius: "°C" },
  main: {
    settings: "Настройки",
    tiles: { power: "Питание", fans: "Вентиляторы", display: "Дисплей и свет", gamepad: "Геймпад" },
    powerNow: (watts) => `сейчас\u00a0${watts}`,
    boost: (on) => (on ? "буст\u00a0вкл" : "буст\u00a0выкл"),
    displaySub: "Насыщенность",
    gamepadSub: "Вибрация ручек",
  },
  settings: {
    title: "Настройки",
    language: "Язык",
    languages: { auto: "Как в Steam", ru: "Русский", en: "English" },
    system: "Система",
    changes: "Изменения в системе",
    changesSummary: (count) =>
      count === 0
        ? "ORIGAMI ничего не менял"
        : `${count} ${pluralForm(locale, count, {
            one: "изменение",
            few: "изменения",
            other: "изменений",
          })} · вернуть всё как было`,
    slogan: ["Любой сгиб можно расправить", "А консоль — сложить под себя"],
  },
  changes: {
    title: "Изменения в системе",
    subtitle: "Настройки · Любой сгиб можно расправить",
    system: "Система",
    device: "Устройство",
    kernel: "Ядро",
    changed: (count) => (count === 0 ? "Что ORIGAMI изменил" : `Что ORIGAMI изменил · ${count}`),
    nothingChanged: "ORIGAMI ничего не менял",
    labels: {},
  },
  errors: { backend: "Бэкенд ORIGAMI не ответил" },
};
