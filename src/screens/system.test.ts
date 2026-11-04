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
    os: { name: "Bazzite", versionId: "45", imageVersion: "45.20261104" },
    kernel: "7.2.15-ogc1.1.fc45.x86_64",
    inputplumber: "0.83.1",
    decky: "v3.3.1",
  },
};

describe("system information", () => {
  it("names the device and the system", () => {
    expect(deviceName(info)).toBe("ROG Xbox Ally X");
    expect(systemName(info)).toBe("Bazzite 45");
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
      ["Bazzite", "45.20261104"],
      ["Ядро", "7.2.15-ogc1.1.fc45.x86_64"],
      ["InputPlumber", "—"],
      ["Decky", "3.3.1"],
    ]);
  });
});
