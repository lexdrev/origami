// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import type { GamePower, Power } from "./backend";
import { chooseOwn, profileOf, summary, withPower, without } from "./gameProfiles";
import { en } from "./i18n/en";
import { ru } from "./i18n/ru";

const NBSP = "\u00a0";
const general: Power = { tdp: 17, headroom: true, cpuBoost: false };
const game = { appId: 1920490, name: "The Outer Worlds" };
const other: GamePower = { appId: 7, name: "Other", power: { tdp: 25, headroom: true, cpuBoost: null }, active: true };

describe("game profiles", () => {
  it("start as a copy of the general settings the first time the game is picked", () => {
    expect(chooseOwn([other], game, general, true)).toEqual([other, { ...game, power: general, active: true }]);
    // Keeping the general settings for a game without a profile makes none.
    expect(chooseOwn([other], game, general, false)).toEqual([other]);
  });

  it("wait with their values while the game runs the general settings", () => {
    const own = { ...game, power: { tdp: 13, headroom: false, cpuBoost: true }, active: true };

    const waiting = chooseOwn([own, other], game, general, false);
    expect(profileOf(waiting, game.appId)).toEqual({ ...own, active: false });
    expect(chooseOwn(waiting, game, general, true)).toEqual([own, other]);
  });

  it("change and go one game at a time", () => {
    const own = { ...game, power: general, active: true };
    const faster = { ...general, tdp: 25 };

    expect(withPower([own, other], game.appId, faster)).toEqual([{ ...own, power: faster }, other]);
    expect(without([own, other], game.appId)).toEqual([other]);
  });

  it("sum up a profile for the list", () => {
    expect(summary({ tdp: 15, headroom: true, cpuBoost: true }, ru)).toBe(
      `TDP${NBSP}15${NBSP}Вт · CPU${NBSP}буст${NBSP}вкл · буст${NBSP}TDP${NBSP}вкл`,
    );
    // A CPU boost left as it is has nothing to say.
    expect(summary({ tdp: 25, headroom: false, cpuBoost: null }, en)).toBe(`TDP${NBSP}25${NBSP}W · TDP${NBSP}boost${NBSP}off`);
  });
});
