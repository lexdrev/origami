// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import type { Telemetry } from "../backend";
import { en } from "../i18n/en";
import { ru } from "../i18n/ru";
import { tileTexts } from "./tiles";

const NBSP = "\u00a0";

const allyX: Telemetry = {
  power: { tdpLimitW: 17, packagePowerW: 16.94, cpuBoost: false },
  fans: { speedsRpm: [4600, 4700], cpuTempC: 61.6, gpuTempC: 63.2 },
  gamepad: { vibrationPct: [50, 50] },
};

describe("tile texts", () => {
  it("show live values in Russian", () => {
    expect(tileTexts(allyX, ru)).toEqual({
      power: { value: `17${NBSP}Вт`, subtitle: `сейчас${NBSP}16,9${NBSP}Вт · буст${NBSP}выкл` },
      fans: { value: `4${NBSP}700`, subtitle: `об/мин · 63${NBSP}°C` },
      display: { value: "—", subtitle: "Насыщенность" },
      gamepad: { value: "50%", subtitle: "Вибрация ручек" },
    });
  });

  it("show both handles when they differ", () => {
    const telemetry = { ...allyX, gamepad: { vibrationPct: [40, 60] as [number, number] } };

    expect(tileTexts(telemetry, en).gamepad.value).toBe("40% / 60%");
  });

  it("show dashes before the first reading and on other hardware", () => {
    const unknown: Telemetry = {
      power: { tdpLimitW: null, packagePowerW: null, cpuBoost: null },
      fans: { speedsRpm: [], cpuTempC: null, gpuTempC: null },
      gamepad: { vibrationPct: null },
    };

    for (const telemetry of [null, unknown]) {
      const texts = tileTexts(telemetry, en);
      expect(texts.power).toEqual({ value: "—", subtitle: "" });
      expect(texts.fans).toEqual({ value: "—", subtitle: "rpm" });
      expect(texts.gamepad.value).toBe("—");
    }
  });
});
