// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { addEventListener, removeEventListener, toaster } from "@decky/api";
import { Router } from "@decky/ui";

import type { ButtonAction } from "./backend";
import { cycleOverlay } from "./overlay";
import { mainWindow, ORIGAMI_TAB, QuickAccessTab, SideMenu, steamTab } from "./quickAccess";
import { actionError, currentMessages, toggleLighting } from "./state";

// The Armoury Crate button does what the settings assign to it (BUGS.md, B17). The backend does
// what it can itself (Steam's chords for the screenshot and the keyboard, the magnifier through
// gamescope) and reports every other press with its action, which ORIGAMI carries out in Steam's
// interface. Menus work the way the quick access button does: a press opens the menu on its tab,
// the next one closes it.

/** Sent by the backend (origami.app.BUTTON_ACTION) with the action of a pressed button. */
const BUTTON_ACTION = "button_action";

/** ORIGAMI's name in Decky (plugin.json), under which Decky opens it inside its own tab. */
const PLUGIN_NAME = "ORIGAMI";

/** Closing a game asks first: the button has to be held again within this time. */
export const CLOSE_CONFIRM_MS = 3000;

const ACTIONS: readonly ButtonAction[] = [
  "none",
  "origami",
  "quick_access",
  "performance",
  "overlay",
  "lighting",
  "screenshot",
  "keyboard",
  "l5",
  "magnifier",
  "close_game",
];

function isButtonAction(value: unknown): value is ButtonAction {
  return ACTIONS.some((action) => action === value);
}

export type MenuAction = Extract<ButtonAction, "origami" | "quick_access" | "performance">;

export interface MenuState {
  open: boolean;
  /** The tab the menu shows, or showed when it was last open. */
  tab: number;
  /** The plugin open inside Decky's tab. */
  deckyPlugin: string | null;
}

export type MenuStep = { kind: "close" } | { kind: "open"; tab: number; deckyPlugin: string | null };

/** What a press with `action` does to the quick access menu; ORIGAMI opens in its own tab if it has one. */
export function stepFor(action: MenuAction, menu: MenuState, ownTab: boolean): MenuStep {
  switch (action) {
    case "quick_access":
      // As Steam's own button: the menu opens on the tab it was left on.
      return menu.open ? { kind: "close" } : { kind: "open", tab: menu.tab, deckyPlugin: null };
    case "performance":
      return toggle(menu, QuickAccessTab.Performance, null);
    case "origami":
      return ownTab ? toggle(menu, ORIGAMI_TAB, null) : toggle(menu, QuickAccessTab.Decky, PLUGIN_NAME);
  }
}

function toggle(menu: MenuState, tab: number, deckyPlugin: string | null): MenuStep {
  const showing = menu.open && menu.tab === tab && (deckyPlugin === null || menu.deckyPlugin === deckyPlugin);
  return showing ? { kind: "close" } : { kind: "open", tab, deckyPlugin };
}

/** Whether a long press closes the game now or asks for one more, given when it last asked. */
export function closeGameStep(askedAt: number | null, now: number): "ask" | "close" {
  return askedAt !== null && now - askedAt <= CLOSE_CONFIRM_MS ? "close" : "ask";
}

// Decky's state (decky-loader frontend/src/components/DeckyState.tsx, v3.3.0): the plugin open
// inside its tab, and the way to open another one there.
interface DeckyState {
  publicState: () => { activePlugin: { name: string } | null };
  setActivePlugin: (name: string) => void;
}

function deckyState(): DeckyState | null {
  const state = window.DeckyPluginLoader?.deckyState;
  if (typeof state !== "object" || state === null) return null;
  const candidate = state as Record<string, unknown>;
  return typeof candidate.publicState === "function" && typeof candidate.setActivePlugin === "function"
    ? (state as DeckyState)
    : null;
}

function readMenu(): MenuState {
  const menus = mainWindow().MenuStore;
  const sideMenu: number = menus.GetOpenSideMenu();
  const tab: number = menus.GetQuickAccessTab();
  return {
    open: sideMenu === SideMenu.QuickAccess,
    tab,
    deckyPlugin: deckyState()?.publicState().activePlugin?.name ?? null,
  };
}

function take(step: MenuStep): void {
  const menus = mainWindow().MenuStore;
  if (step.kind === "close") {
    menus.CloseSideMenus();
    return;
  }
  if (step.deckyPlugin !== null) deckyState()?.setActivePlugin(step.deckyPlugin);
  menus.OpenQuickAccessMenu(steamTab(step.tab));
}

/** Starts carrying out the actions of button presses; returns the function that stops it. */
export function watchButtonActions(ownTabShown: () => boolean): () => void {
  let closeAskedAt: number | null = null;

  const closeGame = () => {
    const t = currentMessages().buttonActions;
    const game = Router.MainRunningApp;
    if (game === undefined) {
      toaster.toast({ title: t.closeGame, body: t.noGame });
      return;
    }
    const now = performance.now();
    if (closeGameStep(closeAskedAt, now) === "close") {
      closeAskedAt = null;
      window.SteamClient.Apps.TerminateApp(String(game.appid), false);
      return;
    }
    closeAskedAt = now;
    toaster.toast({ title: t.closeGame, body: t.holdAgain(game.display_name), duration: CLOSE_CONFIRM_MS });
  };

  const switchLighting = async () => {
    if (await toggleLighting()) return;
    // Pressed with the plugin closed, so its own error line would go unseen.
    toaster.toast({ title: currentMessages().armouryCrate.actions.lighting.name, body: actionError.get() ?? "" });
  };

  const onAction = (action: unknown) => {
    if (!isButtonAction(action)) {
      console.warn("ORIGAMI: unknown button action", action);
      return;
    }
    switch (action) {
      case "origami":
      case "quick_access":
      case "performance":
        take(stepFor(action, readMenu(), ownTabShown()));
        return;
      case "overlay":
        if (!cycleOverlay()) console.warn("ORIGAMI: Steam's performance overlay settings are not there");
        return;
      case "lighting":
        void switchLighting();
        return;
      case "close_game":
        closeGame();
        return;
      case "none":
      case "screenshot":
      case "keyboard":
      case "l5":
      case "magnifier":
        // The backend does these itself and reports no press of a button left alone.
        return;
    }
  };

  addEventListener(BUTTON_ACTION, onAction);
  return () => {
    removeEventListener(BUTTON_ACTION, onAction);
  };
}
