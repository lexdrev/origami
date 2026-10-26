// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { App } from "./App";

/** ORIGAMI in its own quick access tab. Steam draws the tab title above it. */
export function TabApp() {
  return (
    <div className="og-tab-content">
      <App />
    </div>
  );
}
