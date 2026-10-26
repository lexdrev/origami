// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  EARLY_PRESS_MS,
  rescueFor,
  STEAM_REACTION_MS,
  watchQuickAccessButton,
  type SteamMenuState,
} from "./qamAssist";

// Stand-ins for Decky's event bus and Steam's main window, which exist only inside Steam.
const steam = vi.hoisted(() => {
  const open = vi.fn();
  const close = vi.fn();
  const menus = {
    GetOpenSideMenu: (): number => 0,
    GetQuickAccessTab: () => 4, // Quick settings
    OpenQuickAccessMenu: open,
    CloseSideMenus: close,
  };
  return {
    listeners: new Map<string, () => void>(),
    window: { m_flLastQuickAccessPressMS: 0, MenuStore: menus },
    open,
    close,
  };
});

vi.mock("@decky/api", () => ({
  addEventListener: (event: string, listener: () => void) => steam.listeners.set(event, listener),
  removeEventListener: (event: string) => steam.listeners.delete(event),
}));

vi.mock("@decky/ui", () => ({
  Router: { WindowStore: { GamepadUIMainWindowInstance: steam.window } },
}));

const CLOSED = 0;
const MAIN_MENU = 1;
const QUICK_ACCESS = 2;
const QUICK_SETTINGS_TAB = 4;
const state = (lastPressMs: number, openSideMenu: number): SteamMenuState => ({ lastPressMs, openSideMenu });

describe("whether Steam missed a press", () => {
  const reportedAt = 10_000;
  const earlier = reportedAt - 5_000;

  it("leaves a press Steam registered alone", () => {
    expect(rescueFor(state(earlier, CLOSED), state(reportedAt + 80, QUICK_ACCESS), reportedAt)).toBeNull();
  });

  it("leaves it alone when the menu changed, even without a new press time", () => {
    expect(rescueFor(state(earlier, QUICK_ACCESS), state(earlier, CLOSED), reportedAt)).toBeNull();
  });

  it("counts a press Steam registered just before the report as this one", () => {
    const justBefore = reportedAt - EARLY_PRESS_MS / 2;

    expect(rescueFor(state(justBefore, QUICK_ACCESS), state(justBefore, QUICK_ACCESS), reportedAt)).toBeNull();
  });

  it("opens the menu Steam did not open, and closes the one it did not close", () => {
    expect(rescueFor(state(earlier, CLOSED), state(earlier, CLOSED), reportedAt)).toBe("open");
    expect(rescueFor(state(earlier, QUICK_ACCESS), state(earlier, QUICK_ACCESS), reportedAt)).toBe("close");
  });

  it("does nothing over Steam's main menu", () => {
    expect(rescueFor(state(earlier, MAIN_MENU), state(earlier, MAIN_MENU), reportedAt)).toBeNull();
  });
});

describe("watching the button", () => {
  const press = () => steam.listeners.get("qam_pressed")?.();
  let stop: () => void;

  beforeEach(() => {
    vi.useFakeTimers();
    steam.window.m_flLastQuickAccessPressMS = performance.now() - 5_000;
    steam.window.MenuStore.GetOpenSideMenu = () => CLOSED;
    stop = watchQuickAccessButton();
  });

  afterEach(() => {
    stop();
    vi.useRealTimers();
    steam.open.mockClear();
    steam.close.mockClear();
  });

  it("opens the menu after a press Steam missed, on the tab it was left on", () => {
    press();
    vi.advanceTimersByTime(STEAM_REACTION_MS - 1);
    expect(steam.open).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);

    expect(steam.open).toHaveBeenCalledExactlyOnceWith(QUICK_SETTINGS_TAB);
  });

  it("closes the menu after a press Steam missed while it was open", () => {
    steam.window.MenuStore.GetOpenSideMenu = () => QUICK_ACCESS;
    press();

    vi.advanceTimersByTime(STEAM_REACTION_MS);

    expect(steam.close).toHaveBeenCalledOnce();
    expect(steam.open).not.toHaveBeenCalled();
  });

  it("does nothing after a press Steam registered", () => {
    press();
    steam.window.m_flLastQuickAccessPressMS = performance.now() + 80;
    steam.window.MenuStore.GetOpenSideMenu = () => QUICK_ACCESS;

    vi.advanceTimersByTime(STEAM_REACTION_MS);

    expect(steam.open).not.toHaveBeenCalled();
    expect(steam.close).not.toHaveBeenCalled();
  });

  it("stops listening and drops pending checks when stopped", () => {
    press();
    stop();

    vi.advanceTimersByTime(STEAM_REACTION_MS);

    expect(steam.open).not.toHaveBeenCalled();
    expect(steam.listeners.has("qam_pressed")).toBe(false);
  });
});
