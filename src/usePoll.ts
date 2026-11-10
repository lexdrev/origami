// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { useQuickAccessVisible } from "@decky/api";
import { useEffect } from "react";

import { quickAccessOpen } from "./qamTab";
import { useStore } from "./store";

/**
 * Runs `request` again and again, `intervalMs` apart, only while the quick access menu is open: as
 * Decky tells its tab, or as Steam renders the menu, which ORIGAMI's own tab goes by. `request`
 * must stay the same function between renders.
 */
export function usePoll(request: () => Promise<unknown>, intervalMs: number): void {
  const deckyVisible = useQuickAccessVisible();
  const menuOpen = useStore(quickAccessOpen);
  const visible = deckyVisible || menuOpen;

  useEffect(() => {
    if (!visible) return;
    let stopped = false;
    let timer: number | undefined;
    // The next request starts after the previous one finished, so a slow backend
    // never gets a queue of requests.
    const poll = async () => {
      await request();
      if (!stopped) timer = window.setTimeout(() => void poll(), intervalMs);
    };
    void poll();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [visible, request, intervalMs]);
}
