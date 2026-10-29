// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import type { GamePower, Power } from "./backend";
import type { Messages } from "./i18n";
import { withUnit } from "./i18n/format";

// A game can have power settings of its own (ORIGAMI.md, game profiles). The first time the user
// picks the game over the general settings, its profile starts as a copy of them; picking the
// general ones again keeps the profile, waiting, until it is picked again or removed from the list.

/** A game on the Power screen: the one Steam runs, or one picked from the list of profiles. */
export interface Game {
  appId: number;
  name: string;
}

export function profileOf(profiles: readonly GamePower[], appId: number): GamePower | undefined {
  return profiles.find((profile) => profile.appId === appId);
}

/** The profiles after the game is set to run with its own settings or with the general ones. */
export function chooseOwn(profiles: readonly GamePower[], game: Game, general: Power, own: boolean): GamePower[] {
  if (profileOf(profiles, game.appId) === undefined) {
    return own ? [...profiles, { appId: game.appId, name: game.name, power: general, active: true }] : [...profiles];
  }
  return profiles.map((profile) => (profile.appId === game.appId ? { ...profile, active: own } : profile));
}

export function withPower(profiles: readonly GamePower[], appId: number, power: Power): GamePower[] {
  return profiles.map((profile) => (profile.appId === appId ? { ...profile, power } : profile));
}

export function without(profiles: readonly GamePower[], appId: number): GamePower[] {
  return profiles.filter((profile) => profile.appId !== appId);
}

/** What the profile sets, in the words of the Power screen; a boost left as it is has nothing to say. */
export function summary(power: Power, t: Messages): string {
  return [
    `${t.power.tdp}\u00a0${withUnit(String(power.tdp), t.units.watts)}`,
    power.cpuBoost !== null && t.main.boost(power.cpuBoost),
    t.power.tdpBoost(power.headroom),
  ]
    .filter((part) => part !== false)
    .join(" · ");
}
