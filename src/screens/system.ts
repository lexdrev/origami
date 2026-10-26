// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import type { Info } from "../backend";
import type { Messages } from "../i18n";

const SEPARATOR = " · ";

function present(...parts: (string | null)[]): string[] {
  return parts.filter((part): part is string => part !== null && part !== "");
}

/** "ROG Xbox Ally X · Bazzite 44" under the plugin name. */
export function deviceLine(info: Info): string {
  const { device, versions } = info;
  const system = present(versions.os.name, versions.os.versionId).join(" ");
  return present(device.model ?? device.product, system).join(SEPARATOR);
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
