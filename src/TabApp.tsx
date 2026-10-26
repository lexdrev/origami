// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { staticClasses } from "@decky/ui";

import { App } from "./App";

/** ORIGAMI in its own quick access tab: a Steam title row, then the same screens as inside Decky. */
export function TabApp() {
  return (
    <>
      <div className={staticClasses.Title}>ORIGAMI</div>
      <div className="og-tab-content">
        <App />
      </div>
    </>
  );
}
