// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { definePlugin } from "@decky/api";

import { backend } from "./backend";

import { App } from "./App";
import { watchButtonActions } from "./buttonActions";
import { PluginTitle } from "./PluginTitle";
import { watchGameStarts, watchSteamTdpLimit } from "./power";
import { watchQuickAccessButton } from "./qamAssist";
import { createOwnTab } from "./qamTab";
import { loadAll, settings } from "./state";
import { TabApp } from "./TabApp";
import { FoxGlyph } from "./ui/icons";

export default definePlugin(() => {
  // Loaded when Decky starts the plugin, so the first opening shows data at once.
  void loadAll();
  // gamescope forgets ORIGAMI's saturation when it restarts and Steam sets its own as it starts;
  // the plugin loads again after that, so this is the moment to bring ORIGAMI's back.
  backend.restoreSaturation().catch((error: unknown) => {
    console.warn("ORIGAMI: cannot restore the saturation", error);
  });
  // The backend reports quick access presses only while QAM assist is switched on.
  const stopQamAssist = watchQuickAccessButton();
  const ownTab = createOwnTab({ title: null, icon: <FoxGlyph />, content: <TabApp /> });
  // The backend reports presses of the Armoury Crate button only while an action is assigned to it.
  const stopButtonActions = watchButtonActions(() => ownTab?.shown() ?? false);
  // While Steam's own TDP limit is on, ORIGAMI leaves the TDP to it; a game start brings Steam's writes.
  const stopSteamTdpLimit = watchSteamTdpLimit();
  const stopGameStarts = watchGameStarts();
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
      stopQamAssist();
      stopButtonActions();
      stopSteamTdpLimit();
      stopGameStarts();
    },
  };
});
