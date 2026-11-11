// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import type { SoundState } from "./backend";
import { soundOwner, soundStatus } from "./sound";

const playing: SoundState = {
  speakers: true,
  headphones: false,
  running: true,
  owner: null,
  failed: false,
  clockFix: false,
};

describe("the sound's owner", () => {
  it("is the plugin Decky lists, which Decky switches off", () => {
    const listed = { name: "Ally DSP", plugin: true, inDecky: true };
    expect(soundOwner("Ally DSP", playing, null)).toEqual(listed);
    expect(soundOwner("Ally DSP", { ...playing, owner: "Ally DSP" }, ["Ally DSP"])).toEqual(listed);
  });

  it("is else the program whose filter stands in PipeWire", () => {
    // An equaliser inside a bigger plugin that Decky runs, and an app outside Decky.
    const equaliser = { ...playing, running: false, owner: "Panel de Control" };
    expect(soundOwner(null, equaliser, ["ORIGAMI", "Panel de Control"])).toEqual({
      name: "Panel de Control",
      plugin: false,
      inDecky: true,
    });
    const app = { ...playing, running: false, owner: "EasyEffects" };
    expect(soundOwner(null, app, ["ORIGAMI"])).toEqual({ name: "EasyEffects", plugin: false, inDecky: false });
    expect(soundOwner(null, app, null)?.inDecky).toBe(false);
  });

  it("is nobody while neither is there or the state is not read yet", () => {
    expect(soundOwner(null, playing, [])).toBeNull();
    expect(soundOwner(null, null, null)).toBeNull();
  });
});

describe("a switched-on filter", () => {
  it("says why it is not at work", () => {
    expect(soundStatus(null)).toBe("on");
    expect(soundStatus(playing)).toBe("on");
    expect(soundStatus({ ...playing, running: false })).toBe("starting");
    expect(soundStatus({ ...playing, running: false, failed: true })).toBe("failed");
    expect(soundStatus({ ...playing, running: false, headphones: true })).toBe("headphones");
    expect(soundStatus({ ...playing, running: false, speakers: false })).toBe("noSpeakers");
  });
});
