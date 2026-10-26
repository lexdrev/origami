// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { definePlugin } from "@decky/api";

import { App } from "./App";
import { PluginTitle } from "./PluginTitle";
import { installQamTab, SOUNDTRACKS_TAB } from "./qamTab";
import { loadAll } from "./state";
import { TabApp } from "./TabApp";
import { FoxGlyph } from "./ui/icons";

export default definePlugin(() => {
  // Loaded when Decky starts the plugin, so the first opening shows data at once.
  void loadAll();
  const removeTab = installQamTab({ title: null, icon: <FoxGlyph />, content: <TabApp /> }, SOUNDTRACKS_TAB);
  return {
    name: "ORIGAMI",
    titleView: <PluginTitle />,
    icon: <FoxGlyph />,
    content: <App />,
    onDismount() {
      removeTab?.();
    },
  };
});
