// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { definePlugin } from "@decky/api";

import { App } from "./App";
import { loadAll } from "./state";
import { FoxGlyph } from "./ui/icons";

export default definePlugin(() => {
  // Loaded when Decky starts the plugin, so the first opening shows data at once.
  void loadAll();
  return {
    name: "ORIGAMI",
    icon: <FoxGlyph />,
    content: <App />,
  };
});
