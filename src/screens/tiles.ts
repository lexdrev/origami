// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import type { Telemetry, TriggerRumble, Vibration } from "../backend";
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
  /** The sustained limit ORIGAMI holds; while it holds none, the tile shows what asus-armoury shows. */
  tdp: number | null;
  /** Whether the stick lighting is on; undefined while another plugin drives it. */
  lighting: boolean | undefined;
  /** The trigger rumble as chosen, null until then; undefined where ORIGAMI rumbles no triggers. */
  triggers: TriggerRumble | null | undefined;
}

const SEPARATOR = " · ";

const line = (...parts: (string | false)[]) => parts.filter((part) => part !== false).join(SEPARATOR);

/**
 * Current values under the tile names; unknown readings show as a dash. Under the value, what it is
 * and the next thing worth a glance; the styles keep room for two lines, so all tiles stand as tall.
 */
export function tileTexts(telemetry: Telemetry | null, own: OwnValues, t: Messages): TileTexts {
  const number = (value: number, digits = 0) => formatNumber(value, t.locale, digits);
  const power = telemetry?.power;
  const fans = telemetry?.fans;
  const vibration = currentVibration(own.vibration, telemetry);
  const tdp = own.tdp ?? power?.tdpLimitW ?? null;

  const temperatures = [fans?.cpuTempC, fans?.gpuTempC].filter((value) => value != null);
  const hottest = temperatures.length > 0 ? Math.max(...temperatures) : null;
  const fastestFan = fans && fans.speedsRpm.length > 0 ? Math.max(...fans.speedsRpm) : null;

  return {
    power: {
      value: tdp !== null ? withUnit(number(tdp), t.units.watts) : t.unknown,
      subtitle: line(
        power?.packagePowerW != null && t.main.powerNow(withUnit(number(power.packagePowerW, 1), t.units.watts)),
        power?.cpuBoost != null && t.main.boost(power.cpuBoost),
      ),
    },
    fans: {
      value: fastestFan !== null ? number(fastestFan) : t.unknown,
      subtitle: line(t.units.rpm, hottest !== null && withUnit(number(hottest), t.units.celsius)),
    },
    display: {
      value: own.saturation !== null ? `${own.saturation}%` : t.unknown,
      subtitle: line(t.main.displaySub, own.lighting !== undefined && t.main.lighting(own.lighting)),
    },
    gamepad: {
      value: vibration !== null ? formatVibration(vibration, t.gamepad.off) : t.unknown,
      subtitle: line(t.main.gamepadSub, own.triggers !== undefined && t.main.triggers[triggerLine(own.triggers)]),
    },
  };
}

function triggerLine(rumble: TriggerRumble | null): keyof Messages["main"]["triggers"] {
  if (!rumble?.enabled) return "off";
  return rumble.taps ? "taps" : "steady";
}
