// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import type { Sound, SoundWidth, SoundVolume } from "./backend";

/** The volume steps: the speakers as the system has them, and ASUS's two louder ones. */
export const SOUND_VOLUMES: readonly SoundVolume[] = [0, 4, 6];
export const SOUND_WIDTHS: readonly SoundWidth[] = ["off", "moderate", "strong"];

/** What the sound starts with the first time it is switched on (origami.sound.Sound). */
export const DEFAULT_SOUND: Sound = { enabled: true, volumeDb: 4, width: "moderate", voices: true };
