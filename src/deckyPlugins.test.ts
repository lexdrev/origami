// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { afterEach, describe, expect, it, vi } from "vitest";

import { pluginList, watchDeckyPlugins } from "./deckyPlugins";

function decky(names: string[]) {
  const state = { plugins: names.map((name) => ({ name })) };
  const eventBus = new EventTarget();
  vi.stubGlobal("window", { DeckyPluginLoader: { deckyState: { publicState: () => state, eventBus } } });
  return {
    set(next: string[]) {
      state.plugins = next.map((name) => ({ name }));
      eventBus.dispatchEvent(new Event("update"));
    },
    update() {
      eventBus.dispatchEvent(new Event("update"));
    },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Decky's plugins", () => {
  it("are listed by name in a fixed order", () => {
    const listed = pluginList([{ name: "ORIGAMI" }, { name: "HueSync" }]);
    expect(listed).toBe(pluginList([{ name: "HueSync" }, { name: "ORIGAMI" }]));
  });

  it("call back when one is switched on or off, not on other updates", () => {
    const loader = decky(["ORIGAMI"]);
    const changed = vi.fn();
    const stop = watchDeckyPlugins(changed);

    loader.update();
    expect(changed).not.toHaveBeenCalled();
    loader.set(["ORIGAMI", "Fantastic"]);
    loader.set(["ORIGAMI"]);
    expect(changed).toHaveBeenCalledTimes(2);

    stop();
    loader.set(["ORIGAMI", "HueSync"]);
    expect(changed).toHaveBeenCalledTimes(2);
  });
});
