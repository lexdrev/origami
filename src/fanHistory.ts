// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { telemetry } from "./state";
import { createStore } from "./store";

// The fans' speeds over the last minute for the graphs on the Fans screen: one reading a second,
// taken while the quick access menu is open and the telemetry is polled.

const SAMPLES = 60;

export const fanHistory = createStore<readonly (readonly number[])[]>([[], []]);

/** Starts keeping the speeds of every reading. Returns the function that stops it. */
export function recordFanHistory(): () => void {
  return telemetry.subscribe(() => {
    const current = telemetry.get();
    if (current.status !== "ready") return;
    const { speedsRpm } = current.value.fans;
    const history = fanHistory.get();
    fanHistory.set([0, 1].map((fan) => [...(history[fan] ?? []), speedsRpm[fan] ?? 0].slice(-SAMPLES)));
  });
}
