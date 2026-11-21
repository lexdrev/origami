// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { createStore } from "./store";

// A notice is something a screen says once: its tile counts it red until that screen has shown
// it. What was read is kept in Steam's localStorage, so it stays read after Steam restarts.

const READ = "origami.notices";

/** The notices the user has read on their screens. */
export const readNotices = createStore<readonly string[]>([]);

function saved(): readonly string[] {
  let list: unknown;
  try {
    list = JSON.parse(localStorage.getItem(READ) ?? "[]");
  } catch {
    // Text that is no list of notices: nothing has been read.
    return [];
  }
  return Array.isArray(list) ? list.filter((item): item is string => typeof item === "string") : [];
}

/** Takes what was read before Steam restarted. */
export function restoreNotices(): void {
  readNotices.set(saved());
}

/** The notice's screen has shown it: its tile counts it no more. */
export function markRead(notice: string): void {
  const read = readNotices.get();
  if (read.includes(notice)) return;
  const next = [...read, notice];
  readNotices.set(next);
  localStorage.setItem(READ, JSON.stringify(next));
}
