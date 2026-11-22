// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import type { CleanupItem } from "./backend";
import type { Messages } from "./i18n";
import { formatNumber, withUnit } from "./i18n/format";

// What Steam leaves on the disk that can go (origami.cleanup): shader caches, which a game builds
// again, and what a removed game left behind. A prefix holds the game's saves, so the screen says
// for each one whether Steam keeps them in its cloud as well.

const MIB = 2 ** 20;
const GIB = 2 ** 30;

/** Where a removed game's saves are, as far as Steam tells. */
export type Cloud = "cloud" | "local" | "unknown";

/** A size in the binary units Steam itself shows: two decimals under 10 GB, one under 100, then none. */
export function formatSize(bytes: number, t: Messages): string {
  if (bytes < MIB) return t.cleanup.underOneMb;
  if (bytes < GIB) return withUnit(formatNumber(Math.round(bytes / MIB), t.locale), t.units.mb);
  const gb = bytes / GIB;
  return withUnit(formatNumber(gb, t.locale, gb < 10 ? 2 : gb < 100 ? 1 : 0), t.units.gb);
}

/**
 * What removed games left behind: the caches and the prefixes, which have a game to name, then
 * the game folders, of which there may be many small ones. Each part as the backend sorted it,
 * the biggest first.
 */
export function leftovers(items: readonly CleanupItem[]): CleanupItem[] {
  const left = items.filter((item) => item.owner !== "installed");
  return [...left.filter((item) => item.kind !== "folder"), ...left.filter((item) => item.kind === "folder")];
}

/** The shader caches of the games that are installed. */
export function installedCaches(items: readonly CleanupItem[]): CleanupItem[] {
  return items.filter((item) => item.owner === "installed");
}

/**
 * Whether removing the item may cost saves that live nowhere else. A shader cache holds none. A
 * prefix holds the game's, safe only where Steam says its cloud keeps them; a game folder left
 * behind may hold saves and mods, and nothing tells.
 */
export function mayLoseSaves(item: CleanupItem, cloud: Cloud): boolean {
  if (item.kind === "shaders") return false;
  return item.kind === "folder" || item.owner !== "removed" || cloud !== "cloud";
}

/** The leftovers that can go without a second thought, for the button that picks them all. */
export function safeToRemove(
  items: readonly CleanupItem[],
  clouds: Readonly<Record<number, Cloud | undefined>>,
): string[] {
  return leftovers(items)
    .filter((item) => !item.busy && !mayLoseSaves(item, cloudOf(item, clouds)))
    .map((item) => item.key);
}

export function cloudOf(item: CleanupItem, clouds: Readonly<Record<number, Cloud | undefined>>): Cloud {
  return (item.appId === null ? undefined : clouds[item.appId]) ?? "unknown";
}

/** The bytes the picked items take. */
export function pickedSize(items: readonly CleanupItem[], picked: ReadonlySet<string>): number {
  return items.reduce((total, item) => (picked.has(item.key) ? total + item.size : total), 0);
}

/**
 * What a row is called: the installed game's name or the folder's from the backend, the removed
 * game's from Steam (`steamName`), else the game by its number.
 */
export function itemTitle(item: CleanupItem, steamName: string | null, t: Messages): string {
  if (item.name !== null && item.name !== "") return item.name;
  if (steamName !== null) return steamName;
  const id = item.appId ?? 0;
  return item.owner === "shortcut" ? t.cleanup.removedShortcut(id) : t.cleanup.unknownGame(id);
}

export interface ItemNote {
  text: string;
  /** The line warns of saves that would go. */
  danger: boolean;
}

/** The line under a row's size: where the saves are, or why the row cannot be picked now. */
export function itemNote(item: CleanupItem, cloud: Cloud, named: boolean, t: Messages): ItemNote | null {
  if (item.busy) return { text: t.cleanup.busy, danger: false };
  if (item.kind === "shaders") return null;
  if (item.kind === "folder") return { text: t.cleanup.folderNote, danger: true };
  // A game nothing names is told by the folders it made in its prefix.
  const inside = named || item.hints.length === 0 ? "" : ` · ${t.cleanup.inside(item.hints.join(", "))}`;
  if (item.owner === "shortcut") return { text: t.cleanup.shortcutNote + inside, danger: true };
  if (cloud === "cloud") return { text: t.cleanup.cloud + inside, danger: false };
  return { text: (cloud === "local" ? t.cleanup.noCloud : t.cleanup.cloudUnknown) + inside, danger: true };
}
