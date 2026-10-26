// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import type { Telemetry, Vibration } from "../backend";
import type { Messages } from "../i18n";
import { formatNumber, withUnit } from "../i18n/format";
import { currentVibration, formatVibration } from "../vibration";

export interface TileText {
  value: string;
  subtitle: string;
}

export interface TileTexts {
  power: TileText;
  fans: TileText;
  display: TileText;
  gamepad: TileText;
}

/** What ORIGAMI sets itself and reads apart from the telemetry. */
export interface OwnValues {
  /** The saturation gamescope shows. */
  saturation: number | null;
  /** The saved strength; until there is one, the tile shows the driver's. */
  vibration: Vibration | null;
}

const SEPARATOR = " · ";

/** Current values under the tile names; unknown readings show as a dash. */
export function tileTexts(telemetry: Telemetry | null, own: OwnValues, t: Messages): TileTexts {
  const number = (value: number, digits = 0) => formatNumber(value, t.locale, digits);
  const power = telemetry?.power;
  const fans = telemetry?.fans;
  const vibration = currentVibration(own.vibration, telemetry);

  const powerParts = [
    power?.packagePowerW != null && t.main.powerNow(withUnit(number(power.packagePowerW, 1), t.units.watts)),
    power?.cpuBoost != null && t.main.boost(power.cpuBoost),
  ];
  const temperatures = [fans?.cpuTempC, fans?.gpuTempC].filter((value) => value != null);
  const hottest = temperatures.length > 0 ? Math.max(...temperatures) : null;
  const fastestFan = fans && fans.speedsRpm.length > 0 ? Math.max(...fans.speedsRpm) : null;

  return {
    power: {
      value: power?.tdpLimitW != null ? withUnit(number(power.tdpLimitW), t.units.watts) : t.unknown,
      subtitle: powerParts.filter((part) => part !== false).join(SEPARATOR),
    },
    fans: {
      value: fastestFan !== null ? number(fastestFan) : t.unknown,
      subtitle: [t.units.rpm, hottest !== null && withUnit(number(hottest), t.units.celsius)]
        .filter((part) => part !== false)
        .join(SEPARATOR),
    },
    display: { value: own.saturation !== null ? `${own.saturation}%` : t.unknown, subtitle: t.main.displaySub },
    gamepad: {
      value: vibration !== null ? formatVibration(vibration) : t.unknown,
      subtitle: t.main.gamepadSub,
    },
  };
}
