// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { useQuickAccessVisible } from "@decky/api";
import { useEffect } from "react";

import type { Telemetry } from "./backend";
import { refreshHeldPower, refreshTelemetry, telemetry } from "./state";
import { useStore, type Loadable } from "./store";

const POLL_INTERVAL_MS = 1000;

/** Live readings and the limits ORIGAMI holds, polled only while the quick access menu is open. */
export function useTelemetry(): Loadable<Telemetry> {
  const visible = useQuickAccessVisible();

  useEffect(() => {
    if (!visible) return;
    let stopped = false;
    let timer: number | undefined;
    // The next request starts after the previous one finished, so a slow backend
    // never gets a queue of requests.
    const poll = async () => {
      await Promise.all([refreshTelemetry(), refreshHeldPower()]);
      if (!stopped) timer = window.setTimeout(() => void poll(), POLL_INTERVAL_MS);
    };
    void poll();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [visible]);

  return useStore(telemetry);
}
