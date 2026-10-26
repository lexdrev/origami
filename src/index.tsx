// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { definePlugin } from "@decky/api";

import { App } from "./App";
import { PluginTitle } from "./PluginTitle";
import { createOwnTab } from "./qamTab";
import { loadAll, settings } from "./state";
import { TabApp } from "./TabApp";
import { FoxGlyph } from "./ui/icons";

export default definePlugin(() => {
  // Loaded when Decky starts the plugin, so the first opening shows data at once.
  void loadAll();
  const ownTab = createOwnTab({ title: null, icon: <FoxGlyph />, content: <TabApp /> });
  // The tab follows the settings: it appears once they are loaded and moves when they change.
  const unsubscribe = settings.subscribe(() => {
    const current = settings.get();
    if (current.status === "ready") ownTab?.apply(current.value.qamTab, current.value.qamTabBefore);
  });
  return {
    name: "ORIGAMI",
    titleView: <PluginTitle />,
    icon: <FoxGlyph />,
    content: <App />,
    onDismount() {
      unsubscribe();
      ownTab?.dispose();
    },
  };
});
