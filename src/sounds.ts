// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

type SteamSound = Parameters<Window["SteamUIStore"]["GamepadUIAudio"]["PlayNavSound"]>[0];

// @decky/ui has Steam's sound enum only as a type; at runtime the values are plain numbers.
// eslint-disable-next-line @typescript-eslint/no-unsafe-enum-assignment
const steamSound = (value: number): SteamSound => value;

// Steam's own interface sounds, the ones its toggles and buttons play. The numbers are
// Steam's sound enum, read from the Steam client on 2026-10-26.
export const UISound = {
  OutOfScreen: steamSound(14),
  Press: steamSound(21),
} as const;

export type UISound = SteamSound;

/** Plays through Steam, so its interface sound settings apply. */
export function playSound(sound: UISound): void {
  window.SteamUIStore.GamepadUIAudio.PlayNavSound(sound);
}
