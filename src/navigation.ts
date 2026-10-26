// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { createStore, useStore } from "./store";

export type ScreenId = "main" | "settings" | "changes";

const stack = createStore<readonly ScreenId[]>(["main"]);

export function useCurrentScreen(): ScreenId {
  return useStore(stack).at(-1) ?? "main";
}

export function navigate(screen: ScreenId): void {
  stack.set([...stack.get(), screen]);
}

export function back(): void {
  const screens = stack.get();
  if (screens.length > 1) {
    stack.set(screens.slice(0, -1));
  }
}
