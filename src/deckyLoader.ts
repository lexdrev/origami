// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

/** The name in plugin.json, by which Decky Loader knows ORIGAMI. */
export const PLUGIN_NAME = "ORIGAMI";

/** Decky Loader's own message bus, the one its settings pages use; @decky/api has no calls for these routes. */
interface DeckyBackend {
  call: <Result>(route: string, ...args: unknown[]) => Promise<Result>;
}

declare global {
  interface Window {
    DeckyBackend?: DeckyBackend;
  }
}

/** Calls one of Decky Loader's own routes; fails where the loader offers no bus. */
export async function callLoader<Result>(route: string, ...args: unknown[]): Promise<Result> {
  const decky = window.DeckyBackend;
  if (decky === undefined) throw new Error("Decky Loader's message bus is missing");
  return decky.call<Result>(route, ...args);
}
