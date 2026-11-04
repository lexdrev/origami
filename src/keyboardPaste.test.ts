// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { beforeEach, describe, expect, it, vi } from "vitest";

import { fixKeyboardPaste } from "./keyboardPaste";

// Steam's keyboard manager as far as the fix sees it: its paste presses Ctrl+V through Steam.
const steam = vi.hoisted((): { pasted: number; managerClass: unknown } => ({
  pasted: 0,
  managerClass: undefined,
}));

class KeyboardManager {
  declare SendClientPasteCommand: () => void;
}
const steamPaste = () => {
  steam.pasted++;
};

// Decky's replacePatch, as far as the fix relies on it: the original stays reachable and comes back.
vi.mock("@decky/ui", () => ({
  findModuleExport: (filter: (value: unknown) => boolean) =>
    filter(steam.managerClass) ? steam.managerClass : undefined,
  replacePatch: (object: Record<string, unknown>, property: string, handler: (args: unknown[]) => unknown) => {
    const original = object[property] as (...args: unknown[]) => unknown;
    object[property] = function (this: unknown, ...args: unknown[]) {
      return handler.call(this, args);
    };
    return {
      original,
      unpatch: () => {
        object[property] = original;
      },
    };
  },
}));

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("the paste key of Steam's on-screen keyboard", () => {
  beforeEach(() => {
    steam.pasted = 0;
    steam.managerClass = KeyboardManager;
    KeyboardManager.prototype.SendClientPasteCommand = steamPaste;
  });

  it("pastes through ORIGAMI instead of Steam", async () => {
    const paste = vi.fn(() => Promise.resolve(true));
    fixKeyboardPaste(paste);

    new KeyboardManager().SendClientPasteCommand();
    await settle();

    expect(paste).toHaveBeenCalledTimes(1);
    expect(steam.pasted).toBe(0);
  });

  it("lets Steam paste where InputPlumber has no keyboard", async () => {
    fixKeyboardPaste(() => Promise.resolve(false));

    new KeyboardManager().SendClientPasteCommand();
    await settle();

    expect(steam.pasted).toBe(1);
  });

  it("lets Steam paste when ORIGAMI cannot", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    fixKeyboardPaste(() => Promise.reject(new Error("no keyboard")));

    new KeyboardManager().SendClientPasteCommand();
    await settle();

    expect(steam.pasted).toBe(1);
  });

  it("gives Steam its paste back when undone", () => {
    const undo = fixKeyboardPaste(() => Promise.resolve(true));

    undo();

    expect(KeyboardManager.prototype.SendClientPasteCommand).toBe(steamPaste);
  });

  it("does nothing in a Steam without that keyboard", () => {
    steam.managerClass = undefined;
    const paste = vi.fn(() => Promise.resolve(true));

    fixKeyboardPaste(paste)();

    expect(KeyboardManager.prototype.SendClientPasteCommand).toBe(steamPaste);
    expect(paste).not.toHaveBeenCalled();
  });
});
