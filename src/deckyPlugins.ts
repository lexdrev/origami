// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

// Decky's state (decky-loader frontend/src/components/DeckyState.tsx, v3.3.1): the plugins loaded
// now, and an event target that says "update" whenever one of its lists changes. A plugin
// installed, switched on or off, removed or updated changes the list of loaded plugins.
interface DeckyPluginState {
  publicState: () => { plugins: readonly { name: string }[] };
  eventBus: EventTarget;
}

function pluginState(): DeckyPluginState | null {
  const state = window.DeckyPluginLoader?.deckyState;
  if (typeof state !== "object" || state === null) return null;
  const candidate = state as Record<string, unknown>;
  return typeof candidate.publicState === "function" && candidate.eventBus instanceof EventTarget
    ? (state as DeckyPluginState)
    : null;
}

/** The names of the plugins Decky runs now; null when Decky's state cannot be read. */
export function runningPlugins(): string[] | null {
  const state = pluginState();
  return state === null ? null : state.publicState().plugins.map((plugin) => plugin.name);
}

/** The names of the loaded plugins in a fixed order, to tell a change of the list from other updates. */
export function pluginList(plugins: readonly { name: string }[]): string {
  return plugins
    .map((plugin) => plugin.name)
    .sort()
    .join("\n");
}

/** Calls `onChange` whenever the plugins Decky runs change; returns the way to stop. */
export function watchDeckyPlugins(onChange: () => void): () => void {
  const state = pluginState();
  if (state === null) {
    console.warn("ORIGAMI: cannot follow Decky's plugins; they are looked at when a screen opens");
    return () => undefined;
  }
  let last = pluginList(state.publicState().plugins);
  const listener = () => {
    const now = pluginList(state.publicState().plugins);
    if (now === last) return;
    last = now;
    onChange();
  };
  state.eventBus.addEventListener("update", listener);
  return () => {
    state.eventBus.removeEventListener("update", listener);
  };
}
