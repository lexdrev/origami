// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import type { Info } from "../backend";
import type { Messages } from "../i18n";

const SEPARATOR = " · ";

function present(...parts: (string | null)[]): string[] {
  return parts.filter((part): part is string => part !== null && part !== "");
}

/** The console name: the known model, or what DMI reports on other hardware. */
export function deviceName(info: Info): string | null {
  return info.device.model ?? info.device.product;
}

/** "Bazzite 44". */
export function systemName(info: Info): string | null {
  const name = present(info.versions.os.name, info.versions.os.versionId).join(" ");
  return name === "" ? null : name;
}

export function systemFacts(info: Info, t: Messages): [string, string][] {
  const { device, versions } = info;
  const facts: [string, string | null][] = [
    [t.changes.device, present(device.model ?? device.product, device.board).join(SEPARATOR)],
    [versions.os.name ?? "OS", versions.os.imageVersion ?? versions.os.versionId],
    [t.changes.kernel, versions.kernel],
    ["InputPlumber", versions.inputplumber],
    ["Decky", versions.decky?.replace(/^v/, "") ?? null],
  ];
  return facts.map(([term, value]) => [term, value === null || value === "" ? t.unknown : value]);
}
