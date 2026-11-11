// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import type { GamePower, GameSound, Power, Sound } from "./backend";
import {
  chooseOwn,
  chooseOwnSound,
  profileOf,
  soundFor,
  soundSummary,
  summary,
  withPower,
  withSound,
  without,
} from "./gameProfiles";
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

describe("a game's own sound", () => {
  const generalSound: Sound = { enabled: true, volumeDb: 4, width: "moderate", voices: true };
  const quiet: GameSound = { appId: 7, name: "Other", sound: { ...generalSound, enabled: false }, active: true };

  it("starts as a copy of the general sound and waits with its values when switched off", () => {
    const made = chooseOwnSound([quiet], game, generalSound, true);
    expect(made).toEqual([quiet, { ...game, sound: generalSound, active: true }]);
    expect(chooseOwnSound([quiet], game, generalSound, false)).toEqual([quiet]);

    const louder = withSound(made, game.appId, { ...generalSound, volumeDb: 6 });
    const waiting = chooseOwnSound(louder, game, generalSound, false);
    expect(profileOf(waiting, game.appId)).toEqual({ ...game, sound: { ...generalSound, volumeDb: 6 }, active: false });
    expect(without(waiting, 7)).toEqual([profileOf(waiting, game.appId)]);
  });

  it("applies while its game runs and its profile is active", () => {
    const own = { ...game, sound: { ...generalSound, voices: false }, active: true };
    const setting = { sound: generalSound, gameSound: [own, { ...quiet, active: false }] };

    expect(soundFor(setting, game)).toEqual(own.sound);
    expect(soundFor(setting, { appId: 7, name: "Other" })).toBe(generalSound);
    expect(soundFor(setting, { appId: 42, name: "No profile" })).toBe(generalSound);
    expect(soundFor(setting, null)).toBe(generalSound);
    // A game can have its own sound while the general one was never switched on.
    expect(soundFor({ sound: null, gameSound: [own] }, game)).toEqual(own.sound);
    expect(soundFor({ sound: null, gameSound: [own] }, null)).toBeNull();
  });

  it("is told in a line as the tile tells it", () => {
    expect(soundSummary(generalSound, ru)).toBe(`+4${NBSP}дБ · объём${NBSP}умеренно · голоса${NBSP}чётче`);
    expect(soundSummary({ ...generalSound, volumeDb: 0, width: "off", voices: false }, en)).toBe(`Normal · width${NBSP}off`);
    expect(soundSummary(quiet.sound, en)).toBe("Off · the system's sound");
  });
});
