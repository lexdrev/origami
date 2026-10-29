// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { fileURLToPath } from "node:url";

import { defineConfig } from "vite";

const here = (path) => fileURLToPath(new URL(path, import.meta.url));

// The stand renders the plugin screens in a regular browser: Decky libraries are replaced by mocks.
export default defineConfig({
  root: here("."),
  resolve: {
    alias: {
      "@decky/ui": here("mocks/decky-ui.tsx"),
      "@decky/api": here("mocks/decky-api.ts"),
    },
  },
  server: { host: "127.0.0.1", port: 5193, strictPort: true },
  build: { outDir: "dist", emptyOutDir: true },
});
