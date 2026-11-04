// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { findModuleExport, replacePatch } from "@decky/ui";

// The paste key of Steam's on-screen keyboard presses Ctrl+V through SteamClient.Input. gamescope
// passes such keys on without their Ctrl (3.17.0 on Bazzite 44 and 45), so the field gets a plain "v".
// ORIGAMI presses the two keys on InputPlumber's keyboard instead, which gamescope takes as a real
// keyboard, and lets Steam paste its own way when that cannot be done.

interface KeyboardManager {
  SendClientPasteCommand: () => void;
}

function isKeyboardManagerClass(value: unknown): value is { prototype: KeyboardManager } {
  if (typeof value !== "function") return false;
  const prototype: unknown = value.prototype;
  return (
    typeof prototype === "object" &&
    prototype !== null &&
    "SendClientPasteCommand" in prototype &&
    typeof prototype.SendClientPasteCommand === "function"
  );
}

/** Route the paste key of Steam's on-screen keyboard through `paste`; returns the undo. */
export function fixKeyboardPaste(paste: () => Promise<unknown>): () => void {
  const managerClass: unknown = findModuleExport(isKeyboardManagerClass);
  if (!isKeyboardManagerClass(managerClass)) return () => undefined;
  const patch = replacePatch(managerClass.prototype, "SendClientPasteCommand", function (this: KeyboardManager) {
    paste().catch((error: unknown) => {
      console.warn("ORIGAMI: cannot paste through InputPlumber, Steam pastes itself", error);
      patch.original.call(this);
    });
  });
  return () => {
    patch.unpatch();
  };
}
