// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import type { Telemetry } from "./backend";
import { refreshHeldPower, refreshTelemetry, telemetry } from "./state";
import { useStore, type Loadable } from "./store";
import { usePoll } from "./usePoll";

const POLL_INTERVAL_MS = 1000;

const refresh = () => Promise.all([refreshTelemetry(), refreshHeldPower()]);

/** Live readings and the limits ORIGAMI holds, polled only while the quick access menu is open. */
export function useTelemetry(): Loadable<Telemetry> {
  usePoll(refresh, POLL_INTERVAL_MS);
  return useStore(telemetry);
}
