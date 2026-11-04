// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import type { Info } from "../backend";
import type { Messages } from "../i18n";

const SEPARATOR = " · ";

function present(...parts: (string | null)[]): string[] {
  return parts.filter((part): part is string => part !== null && part !== "");
}

/**
 * The console name: the known model, or what DMI reports on other hardware without the board's code,
 * which ASUS repeats there ("ROG Ally RC71L_RC71L" is "ROG Ally").
 */
export function deviceName(info: Info): string | null {
  const { model, product, board } = info.device;
  if (model !== null) return model;
  if (product === null || board === null || board === "") return product;
  const code = board.toLowerCase();
  const words = product.split(/\s+/).filter((word) => !word.toLowerCase().includes(code));
  return words.length > 0 ? words.join(" ") : product;
}

/**
 * The system's version as it calls it: the image's build where there is one ("45.20261104" on
 * Bazzite), SteamOS's version with its build apart ("3.9.5 · 20261023.100"), else the version.
 */
export function systemVersion(info: Info): string | null {
  const { id, versionId, imageVersion, buildId } = info.versions.os;
  if (imageVersion !== null && imageVersion !== "") return imageVersion;
  if (id === "steamos" && buildId !== null && buildId !== "") return present(versionId, buildId).join(SEPARATOR);
  return versionId;
}

/** "Bazzite 45.20261104", "SteamOS 3.9.5 · 20261023.100". */
export function systemName(info: Info): string | null {
  const name = present(info.versions.os.name, systemVersion(info)).join(" ");
  return name === "" ? null : name;
}

export function systemFacts(info: Info, t: Messages): [string, string][] {
  const { device, versions } = info;
  const facts: [string, string | null][] = [
    [t.changes.device, present(deviceName(info), device.board).join(SEPARATOR)],
    [versions.os.name ?? "OS", systemVersion(info)],
    [t.changes.kernel, versions.kernel],
    ["InputPlumber", versions.inputplumber],
    ["Decky", versions.decky?.replace(/^v/, "") ?? null],
  ];
  return facts.map(([term, value]) => [term, value === null || value === "" ? t.unknown : value]);
}
