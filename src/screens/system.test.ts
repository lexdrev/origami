// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { describe, expect, it } from "vitest";

import type { Info } from "../backend";
import { ru } from "../i18n/ru";
import { deviceName, systemFacts, systemName } from "./system";

const info: Info = {
  version: "0.1.0",
  device: { board: "RC73XA", product: "ROG Xbox Ally X RC73XA_RC73XA", model: "ROG Xbox Ally X" },
  versions: {
    os: { name: "Bazzite", versionId: "44", imageVersion: "44.20261023" },
    kernel: "7.2.9-ogc3.1.fc44.x86_64",
    inputplumber: "0.83.0",
    decky: "v3.3.0",
  },
};

describe("system information", () => {
  it("names the device and the system", () => {
    expect(deviceName(info)).toBe("ROG Xbox Ally X");
    expect(systemName(info)).toBe("Bazzite 44");
  });

  it("falls back to the DMI product name on other hardware", () => {
    const other = { ...info, device: { board: "X", product: "Some Handheld", model: null } };

    expect(deviceName(other)).toBe("Some Handheld");
  });

  it("has no system name without os-release", () => {
    const bare = { ...info, versions: { ...info.versions, os: { name: null, versionId: null, imageVersion: null } } };

    expect(systemName(bare)).toBeNull();
  });

  it("lists versions, with dashes for what is unknown", () => {
    const partial = { ...info, versions: { ...info.versions, inputplumber: null } };

    expect(systemFacts(partial, ru)).toEqual([
      ["Устройство", "ROG Xbox Ally X · RC73XA"],
      ["Bazzite", "44.20261023"],
      ["Ядро", "7.2.9-ogc3.1.fc44.x86_64"],
      ["InputPlumber", "—"],
      ["Decky", "3.3.0"],
    ]);
  });
});
