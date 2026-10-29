// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { staticClasses } from "@decky/ui";

import { App } from "./App";
import { PluginTitle } from "./PluginTitle";

/**
 * ORIGAMI in its own quick access tab. Like Decky's tab, it draws Steam's large white title
 * itself; the tab is registered without a title, which Steam would show small at the edge.
 */
export function TabApp() {
  return (
    <>
      <div className={`${staticClasses.Title} og-tab-title`}>
        <PluginTitle />
      </div>
      <div className="og-tab-content">
        <App />
      </div>
    </>
  );
}
