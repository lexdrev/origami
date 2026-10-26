// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { useSyncExternalStore } from "react";

// State lives at module level: the QAM unmounts the plugin view when it closes,
// and values must not reset or flash when it opens again.

export interface Store<T> {
  get: () => T;
  set: (value: T) => void;
  subscribe: (listener: () => void) => () => void;
}

export function createStore<T>(initial: T): Store<T> {
  let value = initial;
  const listeners = new Set<() => void>();
  return {
    get: () => value,
    set(next) {
      if (Object.is(next, value)) return;
      value = next;
      listeners.forEach((listener) => {
        listener();
      });
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

export function useStore<T>(store: Store<T>): T {
  return useSyncExternalStore(store.subscribe, store.get);
}

export type Loadable<T> =
  | { status: "loading" }
  | { status: "ready"; value: T }
  | { status: "failed"; error: string };

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
