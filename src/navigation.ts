// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { playSound, UISound } from "./sounds";
import { createStore, useStore } from "./store";

export type ScreenId = "main" | "settings" | "changes";

const stack = createStore<readonly ScreenId[]>(["main"]);

export function useCurrentScreen(): ScreenId {
  return useStore(stack).at(-1) ?? "main";
}

// Screen changes play Steam's transition sounds here, so the back button and B sound the same.

export function navigate(screen: ScreenId): void {
  stack.set([...stack.get(), screen]);
  playSound(UISound.IntoScreen);
}

export function back(): void {
  const screens = stack.get();
  if (screens.length > 1) {
    stack.set(screens.slice(0, -1));
    playSound(UISound.OutOfScreen);
  }
}
