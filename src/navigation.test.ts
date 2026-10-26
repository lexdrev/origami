// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { back, navigate } from "./navigation";
import { UISound } from "./sounds";

const playNavSound = vi.fn();

beforeEach(() => {
  vi.stubGlobal("window", { SteamUIStore: { GamepadUIAudio: { PlayNavSound: playNavSound } } });
});

afterEach(() => {
  vi.unstubAllGlobals();
  playNavSound.mockClear();
});

describe("navigation sounds", () => {
  it("click into a screen and play Steam's back sound out of it", () => {
    navigate("settings");
    back();

    expect(playNavSound.mock.calls).toEqual([[UISound.Press], [UISound.OutOfScreen]]);
  });

  it("stay silent when there is nowhere to go back to", () => {
    back();

    expect(playNavSound).not.toHaveBeenCalled();
  });
});
