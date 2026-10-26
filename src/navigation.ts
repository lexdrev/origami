// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { playSound, UISound } from "./sounds";
import { createStore, useStore } from "./store";

export type ScreenId = "main" | "display" | "customColour" | "gamepad" | "settings" | "qamTab" | "changes";

const stack = createStore<readonly ScreenId[]>(["main"]);

export function useCurrentScreen(): ScreenId {
  return useStore(stack).at(-1) ?? "main";
}

// Screen changes play their sounds here, so the back button and B sound the same. Opening a
// screen clicks like opening a plugin from the Decky list.

export function navigate(screen: ScreenId): void {
  stack.set([...stack.get(), screen]);
  playSound(UISound.Press);
}

export function back(): void {
  const screens = stack.get();
  if (screens.length > 1) {
    stack.set(screens.slice(0, -1));
    playSound(UISound.OutOfScreen);
  }
}
