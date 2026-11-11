// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import type { Sound, Telemetry, TriggerRumble } from "../backend";
import { en } from "../i18n/en";
import { ru } from "../i18n/ru";
import { tileTexts } from "./tiles";

const NBSP = "\u00a0";
const none = {
  saturation: null,
  vibration: undefined,
  tdp: null,
  lighting: undefined,
  triggers: undefined,
  fanCurve: undefined,
  sound: undefined,
  soundState: null,
};

const allyX: Telemetry = {
  power: {
    tdpLimitW: 35,
    tdpTopW: 35,
    batteryTdpTopW: null,
    packagePowerW: 16.94,
    cpuBoost: false,
    onBattery: false,
    battery: null,
  },
  fans: { speedsRpm: [4600, 4700], cpuTempC: 61.6, gpuTempC: 63.2 },
  gamepad: { vibrationPct: [50, 50] },
};

describe("tile texts", () => {
  it("show live values in Russian", () => {
    const own = { ...none, saturation: 150, tdp: 17, lighting: true, triggers: null, fanCurve: null, sound: null };

    expect(tileTexts(allyX, own, ru)).toEqual({
      power: { value: `17${NBSP}Вт`, subtitle: `сейчас${NBSP}16,9${NBSP}Вт · CPU${NBSP}буст${NBSP}выкл` },
      fans: { value: `4${NBSP}700`, subtitle: `об/мин · 63${NBSP}°C · кривая${NBSP}·${NBSP}Дефолт` },
      display: { value: "150%", subtitle: `Насыщенность · подсветка${NBSP}вкл` },
      gamepad: { value: "50%", subtitle: `Вибрация ручек · триггеры${NBSP}выкл` },
      sound: { value: "Выкл", subtitle: `Динамики как в${NBSP}системе` },
    });
  });

  it("show the volume step and what else the sound does", () => {
    const sound: Sound = { enabled: true, volumeDb: 4, width: "moderate", voices: true };
    const text = (own: Partial<Sound>) => tileTexts(allyX, { ...none, sound: { ...sound, ...own } }, ru).sound;

    expect(text({})).toEqual({ value: `+4${NBSP}дБ`, subtitle: `объём${NBSP}умеренно · голоса${NBSP}чётче` });
    expect(text({ volumeDb: 0, width: "off", voices: false })).toEqual({ value: "Обычная", subtitle: `объём${NBSP}выкл` });
    expect(text({ enabled: false }).value).toBe("Выкл");
  });

  it("say why a switched-on filter is not at work", () => {
    const sound: Sound = { enabled: true, volumeDb: 4, width: "moderate", voices: true };
    const playing = {
      speakers: true,
      headphones: false,
      running: true,
      owner: null,
      failed: false,
      clockFix: false,
    };
    const text = (state: Partial<typeof playing>, own: Partial<Sound> = {}) =>
      tileTexts(allyX, { ...none, sound: { ...sound, ...own }, soundState: { ...playing, ...state } }, ru).sound;

    expect(text({}).value).toBe(`+4${NBSP}дБ`);
    expect(text({ headphones: true, running: false })).toEqual({ value: "Пауза", subtitle: "Наушники подключены" });
    expect(text({ speakers: false, running: false })).toEqual({ value: "—", subtitle: `Динамики не${NBSP}найдены` });
    expect(text({ running: false, failed: true })).toEqual({ value: "—", subtitle: `Не${NBSP}запустилась` });
    // Still coming up, it shows as at work; switched off, the headphones do not matter.
    expect(text({ running: false }).value).toBe(`+4${NBSP}дБ`);
    expect(text({ headphones: true, running: false }, { enabled: false }).value).toBe("Выкл");
  });

  it("say another plugin has the sound only once that is known", () => {
    expect(tileTexts(allyX, none, en).sound).toEqual({ value: "—", subtitle: "Another plugin" });
    expect(tileTexts(allyX, { ...none, sound: "unknown" }, en).sound).toEqual({ value: "—", subtitle: "" });
    expect(tileTexts(allyX, { ...none, sound: "program" }, ru).sound).toEqual({
      value: "—",
      subtitle: "Другая программа",
    });
  });

  it("show how the triggers rumble", () => {
    const rumble = { enabled: true, triggers: "both", level: "medium", taps: false } as const;
    const subtitle = (triggers: TriggerRumble | null) => tileTexts(allyX, { ...none, triggers }, ru).gamepad.subtitle;

    expect(subtitle({ ...rumble, enabled: false })).toBe(`Вибрация ручек · триггеры${NBSP}выкл`);
    expect(subtitle(rumble)).toBe(`Вибрация ручек · триггеры${NBSP}вкл`);
    expect(subtitle({ ...rumble, taps: true })).toBe(`Вибрация ручек · триггеры${NBSP}толчками`);
  });

  it("leave out what other plugins drive", () => {
    const texts = tileTexts(allyX, none, en);

    expect(texts.display.subtitle).toBe("Saturation");
    expect(texts.gamepad.subtitle).toBe("Handle vibration");
  });

  it("show both handles when they differ", () => {
    const telemetry = { ...allyX, gamepad: { vibrationPct: [40, 60] as [number, number] } };

    expect(tileTexts(telemetry, none, en).gamepad.value).toBe("40 / 60%");
  });

  it("show the strength ORIGAMI keeps, which the driver does not know", () => {
    const own = { ...none, vibration: { enabled: true, left: 25, right: 25 } };

    expect(tileTexts(allyX, own, en).gamepad.value).toBe("25%");
  });

  it("show a dash while the strength was never set, as the driver's is not on ORIGAMI's scale", () => {
    expect(tileTexts(allyX, { ...none, vibration: null }, en).gamepad.value).toBe("—");
  });

  it("show what asus-armoury shows while ORIGAMI holds no TDP", () => {
    expect(tileTexts(allyX, none, en).power.value).toBe(`35${NBSP}W`);
  });

  it("show dashes before the first reading and on other hardware", () => {
    const unknown: Telemetry = {
      power: {
        tdpLimitW: null,
        tdpTopW: null,
        batteryTdpTopW: null,
        packagePowerW: null,
        cpuBoost: null,
        onBattery: false,
        battery: null,
      },
      fans: { speedsRpm: [], cpuTempC: null, gpuTempC: null },
      gamepad: { vibrationPct: null },
    };

    for (const telemetry of [null, unknown]) {
      const texts = tileTexts(telemetry, none, en);
      expect(texts.power).toEqual({ value: "—", subtitle: "" });
      expect(texts.fans).toEqual({ value: "—", subtitle: "rpm" });
      expect(texts.gamepad.value).toBe("—");
    }
  });
});
