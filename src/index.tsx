// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { definePlugin } from "@decky/api";

import { App } from "./App";
import { loadAll } from "./state";
import { TitleBar } from "./TitleBar";
import { FoxGlyph } from "./ui/icons";

export default definePlugin(() => {
  // Loaded when Decky starts the plugin, so the first opening shows data at once.
  void loadAll();
  return {
    name: "ORIGAMI",
    titleView: <TitleBar />,
    icon: <FoxGlyph />,
    content: <App />,
  };
});
