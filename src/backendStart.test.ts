// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Settings } from "./backend";
import { BACKEND_WAIT_MS, isOldDecky, missingBackend, watchBackendStart } from "./backendStart";
import { settings } from "./state";

// The backend, which Decky reaches only inside Steam; these tests set its answers in the store.
vi.mock("./backend", () => ({ backend: {} }));

describe("isOldDecky", () => {
  it("finds Decky Loader releases built with Python 3.11", () => {
    expect(isOldDecky("v3.2.10")).toBe(true);
    expect(isOldDecky("v3.0.0")).toBe(true);
    expect(isOldDecky("v2.12.0")).toBe(true);
  });

  it("passes 3.3.0 and newer, pre-releases included", () => {
    expect(isOldDecky("v3.3.0")).toBe(false);
    expect(isOldDecky("v3.3.0-pre1")).toBe(false);
    expect(isOldDecky("v3.3.1")).toBe(false);
    expect(isOldDecky("v4.0.0")).toBe(false);
  });

  it("passes versions it cannot read", () => {
    expect(isOldDecky("dev")).toBe(false);
    expect(isOldDecky("unknown")).toBe(false);
  });
});

describe("watchBackendStart", () => {
  const deckyVersion = (current: string) => {
    vi.stubGlobal("window", { DeckyBackend: { call: () => Promise.resolve({ current }) } });
  };
  let stop: () => void = () => undefined;

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    stop();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    settings.set({ status: "loading" });
    missingBackend.set(null);
  });

  it("names an old Decky at once", async () => {
    deckyVersion("v3.2.10");
    stop = watchBackendStart();
    await vi.advanceTimersByTimeAsync(0);
    expect(missingBackend.get()).toEqual({ reason: "oldDecky", deckyVersion: "3.2.10" });
    await vi.advanceTimersByTimeAsync(BACKEND_WAIT_MS);
    expect(missingBackend.get()).toEqual({ reason: "oldDecky", deckyVersion: "3.2.10" });
  });

  it("says the backend is silent once the wait is over", async () => {
    deckyVersion("v3.3.1");
    stop = watchBackendStart();
    await vi.advanceTimersByTimeAsync(BACKEND_WAIT_MS - 1);
    expect(missingBackend.get()).toBeNull();
    await vi.advanceTimersByTimeAsync(1);
    expect(missingBackend.get()).toEqual({ reason: "silent" });
  });

  it("stays quiet when the backend answers in time", async () => {
    deckyVersion("v3.3.1");
    stop = watchBackendStart();
    settings.set({ status: "ready", value: {} as Settings });
    await vi.advanceTimersByTimeAsync(BACKEND_WAIT_MS);
    expect(missingBackend.get()).toBeNull();
  });

  it("waits out the silence when Decky cannot tell its version", async () => {
    vi.stubGlobal("window", { DeckyBackend: { call: () => Promise.reject(new Error("no route")) } });
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    stop = watchBackendStart();
    await vi.advanceTimersByTimeAsync(BACKEND_WAIT_MS);
    expect(missingBackend.get()).toEqual({ reason: "silent" });
  });
});
