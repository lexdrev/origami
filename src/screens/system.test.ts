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
    os: {
      id: "bazzite",
      name: "Bazzite",
      versionId: "45",
      imageVersion: "45.20261104",
      buildId: "Stable (F45.20261104)",
    },
    kernel: "7.2.15-ogc1.1.fc45.x86_64",
    inputplumber: "0.83.1",
    decky: "v3.3.1",
  },
  buttons: ["armoury_crate", "armoury_crate_hold", "quick_access"],
};

const steamos: Info = {
  version: "0.1.0",
  device: { board: "RC71L", product: "ROG Ally RC71L_RC71L", model: "ROG Ally" },
  versions: {
    os: { id: "steamos", name: "SteamOS", versionId: "3.9.5", imageVersion: null, buildId: "20261023.100" },
    kernel: "7.2.7-valve2-2-neptune-72-g31504582a073",
    inputplumber: "0.78.0",
    decky: "v3.3.1",
  },
  buttons: [],
};

const noOs = { id: null, name: null, versionId: null, imageVersion: null, buildId: null };

describe("system information", () => {
  it("names the device and the system with the image's build", () => {
    expect(deviceName(info)).toBe("ROG Xbox Ally X");
    expect(systemName(info)).toBe("Bazzite 45.20261104");
  });

  it("shows SteamOS's version with its build apart", () => {
    expect(systemName(steamos)).toBe("SteamOS 3.9.5 · 20261023.100");
  });

  it("keeps the version alone where the system has no build", () => {
    const os = { ...noOs, id: "arch", name: "Arch Linux", versionId: "1" };
    const plain = { ...info, versions: { ...info.versions, os } };

    expect(systemName(plain)).toBe("Arch Linux 1");
  });

  it("falls back to the DMI product name on other hardware", () => {
    const other = { ...info, device: { board: "X", product: "Some Handheld", model: null } };

    expect(deviceName(other)).toBe("Some Handheld");
  });

  it("drops the board's code from the DMI name of an unknown model", () => {
    const unknown = { ...info, device: { board: "RC99XX", product: "ROG Ally Next RC99XX_RC99XX", model: null } };

    expect(deviceName(unknown)).toBe("ROG Ally Next");
  });

  it("has no system name without os-release", () => {
    const bare = { ...info, versions: { ...info.versions, os: noOs } };

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

  it("lists SteamOS with its build", () => {
    expect(systemFacts(steamos, ru).slice(0, 2)).toEqual([
      ["Устройство", "ROG Ally · RC71L"],
      ["SteamOS", "3.9.5 · 20261023.100"],
    ]);
  });
});
