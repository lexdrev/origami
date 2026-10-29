// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CLOSE_CONFIRM_MS, closeGameStep, stepFor, watchButtonActions, type MenuState } from "./buttonActions";
import { ru } from "./i18n/ru";
import { ORIGAMI_TAB, QuickAccessTab } from "./quickAccess";

// Stand-ins for Decky's event bus, toasts and state, Steam's main window and running game, and
// ORIGAMI's own state and overlay modules, which reach Steam only inside it.
const steam = vi.hoisted(() => {
  const menus = {
    sideMenu: 0,
    tab: 4,
    GetOpenSideMenu(): number {
      return this.sideMenu;
    },
    GetQuickAccessTab(): number {
      return this.tab;
    },
    OpenQuickAccessMenu(tab: number) {
      this.sideMenu = 2;
      this.tab = tab;
    },
    CloseSideMenus() {
      this.sideMenu = 0;
    },
  };
  const decky = {
    active: null as string | null,
    publicState() {
      return { activePlugin: this.active === null ? null : { name: this.active } };
    },
    setActivePlugin(name: string) {
      this.active = name;
    },
  };
  return {
    listeners: new Map<string, (action: unknown) => void>(),
    menus,
    decky,
    router: { MainRunningApp: undefined as { appid: number; display_name: string } | undefined },
    toasts: [] as { title: string; body: string }[],
    lightingSwitches: true,
    overlayCycles: 0,
  };
});

vi.mock("@decky/api", () => ({
  addEventListener: (event: string, listener: (action: unknown) => void) => steam.listeners.set(event, listener),
  removeEventListener: (event: string) => steam.listeners.delete(event),
  toaster: { toast: (toast: { title: string; body: string }) => steam.toasts.push(toast) },
}));

vi.mock("@decky/ui", () => ({
  Router: Object.assign(steam.router, { WindowStore: { GamepadUIMainWindowInstance: { MenuStore: steam.menus } } }),
}));

vi.mock("./state", async () => {
  const { ru: messages } = await import("./i18n/ru");
  return {
    actionError: { get: () => "Lighting Plugin drives the stick lighting" },
    currentMessages: () => messages,
    toggleLighting: () => Promise.resolve(steam.lightingSwitches),
  };
});

vi.mock("./overlay", () => ({
  cycleOverlay: () => {
    steam.overlayCycles += 1;
    return true;
  },
}));

const QUICK_SETTINGS = 4;
const closed: MenuState = { open: false, tab: QUICK_SETTINGS, deckyPlugin: null };
const openOn = (tab: number, deckyPlugin: string | null = null): MenuState => ({ open: true, tab, deckyPlugin });

describe("what a press does to the quick access menu", () => {
  it("opens ORIGAMI's own tab, and closes it on the next press", () => {
    expect(stepFor("origami", closed, true)).toEqual({ kind: "open", tab: ORIGAMI_TAB, deckyPlugin: null });
    expect(stepFor("origami", openOn(ORIGAMI_TAB), true)).toEqual({ kind: "close" });
  });

  it("switches to ORIGAMI when the menu shows another tab", () => {
    const origami = { kind: "open", tab: ORIGAMI_TAB, deckyPlugin: null };
    expect(stepFor("origami", openOn(QUICK_SETTINGS), true)).toEqual(origami);
  });

  it("opens ORIGAMI inside Decky's tab without a tab of its own", () => {
    const decky = QuickAccessTab.Decky;
    const origami = { kind: "open", tab: decky, deckyPlugin: "ORIGAMI" };
    expect(stepFor("origami", closed, false)).toEqual(origami);
    expect(stepFor("origami", openOn(decky, "Another Plugin"), false)).toEqual(origami);
    expect(stepFor("origami", openOn(decky, "ORIGAMI"), false)).toEqual({ kind: "close" });
  });

  it("works as the quick access button: the last tab, or closed", () => {
    expect(stepFor("quick_access", closed, true)).toEqual({ kind: "open", tab: QUICK_SETTINGS, deckyPlugin: null });
    expect(stepFor("quick_access", openOn(ORIGAMI_TAB), true)).toEqual({ kind: "close" });
  });

  it("opens Steam's performance tab", () => {
    const performance = QuickAccessTab.Performance;
    expect(stepFor("performance", closed, true)).toEqual({ kind: "open", tab: performance, deckyPlugin: null });
    expect(stepFor("performance", openOn(performance), true)).toEqual({ kind: "close" });
  });
});

describe("closing the game", () => {
  it("asks first and closes on a second long press soon after", () => {
    expect(closeGameStep(null, 10_000)).toBe("ask");
    expect(closeGameStep(10_000, 10_000 + CLOSE_CONFIRM_MS - 1)).toBe("close");
    expect(closeGameStep(10_000, 10_000 + CLOSE_CONFIRM_MS + 1)).toBe("ask");
  });
});

describe("carrying out a press", () => {
  const terminate = vi.fn();

  beforeEach(() => {
    vi.stubGlobal("window", {
      DeckyPluginLoader: { deckyState: steam.decky },
      SteamClient: { Apps: { TerminateApp: terminate } },
    });
  });

  afterEach(() => {
    Object.assign(steam.menus, { sideMenu: 0, tab: QUICK_SETTINGS });
    Object.assign(steam, { toasts: [], lightingSwitches: true, overlayCycles: 0 });
    steam.decky.active = null;
    steam.router.MainRunningApp = undefined;
    terminate.mockClear();
    vi.unstubAllGlobals();
  });

  const press = (action: unknown) => {
    steam.listeners.get("button_action")?.(action);
  };

  it("opens ORIGAMI inside Decky and closes it again", () => {
    const stop = watchButtonActions(() => false);

    press("origami");
    expect([steam.menus.sideMenu, steam.menus.tab, steam.decky.active]).toEqual([2, QuickAccessTab.Decky, "ORIGAMI"]);
    press("origami");
    expect(steam.menus.sideMenu).toBe(0);

    stop();
    expect(steam.listeners.has("button_action")).toBe(false);
  });

  it("shows the overlay a level more detailed on every press", () => {
    const stop = watchButtonActions(() => true);

    press("overlay");
    press("overlay");

    expect(steam.overlayCycles).toBe(2);
    stop();
  });

  it("closes the running game only when the button is held again", () => {
    steam.router.MainRunningApp = { appid: 1920490, display_name: "The Outer Worlds" };
    const stop = watchButtonActions(() => true);

    press("close_game");
    expect(terminate).not.toHaveBeenCalled();
    expect(steam.toasts).toEqual([
      {
        title: ru.buttonActions.closeGame,
        body: ru.buttonActions.holdAgain("The Outer Worlds"),
        duration: CLOSE_CONFIRM_MS,
      },
    ]);

    press("close_game");
    expect(terminate).toHaveBeenCalledWith("1920490", false);
    stop();
  });

  it("says so when there is no game to close", () => {
    const stop = watchButtonActions(() => true);

    press("close_game");

    expect(steam.toasts).toEqual([{ title: ru.buttonActions.closeGame, body: ru.buttonActions.noGame }]);
    stop();
  });

  it("tells why the lighting did not switch, as the plugin may be closed", async () => {
    steam.lightingSwitches = false;
    const stop = watchButtonActions(() => true);

    press("lighting");
    await Promise.resolve();
    await Promise.resolve();

    expect(steam.toasts).toEqual([{ title: "Подсветка стиков", body: "Lighting Plugin drives the stick lighting" }]);
    stop();
  });

  it("leaves Steam's chords to the backend and ignores actions it does not know", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const stop = watchButtonActions(() => true);

    press("screenshot");
    press("dance");

    expect([steam.menus.sideMenu, steam.toasts.length]).toEqual([0, 0]);
    expect(warn).toHaveBeenCalledTimes(1);
    stop();
    warn.mockRestore();
  });
});
