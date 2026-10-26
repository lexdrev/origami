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

/**
 * Sends only the newest value: while one is on its way, later ones replace each other, so a
 * slider moved quickly does not queue up a request for every step.
 */
export function latestOnly<T>(send: (value: T) => Promise<unknown>) {
  let busy = false;
  let pending: { value: T } | null = null;

  const run = async (value: T): Promise<void> => {
    busy = true;
    try {
      await send(value);
    } finally {
      busy = false;
      const next = pending;
      pending = null;
      if (next) void run(next.value);
    }
  };

  return {
    send(value: T): void {
      if (busy) pending = { value };
      else void run(value);
    },
    /** Forgets a value not sent yet. */
    drop(): void {
      pending = null;
    },
  };
}

export type Loadable<T> =
  | { status: "loading" }
  | { status: "ready"; value: T }
  | { status: "failed"; error: string };

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
