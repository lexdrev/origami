// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { pluralForm } from "./format";
import type { Messages } from "./index";

const locale = "ru-RU";

export const ru: Messages = {
  locale,
  unknown: "—",
  actions: { open: "Открыть", back: "Назад", select: "Выбрать", toggle: "Переключить" },
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
    qamTab: "Вкладка в быстром меню",
    qamTabOff: "Выкл · только внутри Decky",
    qamTabFirst: "Вкл · первая в колонке",
    qamTabLast: "Вкл · последняя в колонке",
    qamTabArranged: (plugin) => `Вкл · место задаёт ${plugin ?? "другой плагин"}`,
    qamTabAbove: (tab) => `Вкл · над вкладкой «${tab}»`,
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
  qamTab: {
    title: "Вкладка ORIGAMI",
    subtitle: "Настройки · быстрое меню",
    own: "Отдельная вкладка",
    ownOn: "Лиса в колонке быстрого меню",
    ownOff: "Только внутри вкладки Decky",
    place: "Место в колонке",
    placeHint: "Двигайте ORIGAMI выше или ниже.",
    arranged: (plugin) => `Порядком управляет ${plugin ?? "другой плагин"}`,
    arrangedText:
      "ORIGAMI не двигает свою вкладку, чтобы ему не мешать. Без него место снова можно выбирать здесь.",
    up: "Выше",
    down: "Ниже",
    toTop: "В начало",
    toBottom: "В конец",
  },
  tabs: {
    notifications: "Уведомления",
    remotePlay: "Remote Play Together",
    voiceChat: "Голосовой чат",
    friends: "Друзья",
    quickSettings: "Быстрые настройки",
    performance: "Производительность",
    help: "Помощь",
    soundtracks: "Саундтреки",
    decky: "Decky",
    plugin: "Плагин",
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
