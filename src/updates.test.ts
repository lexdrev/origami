// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  checkDaily,
  checkForUpdates,
  currentVersion,
  DAY_MS,
  forgetLastCheck,
  installUpdate,
  isNewer,
  readRelease,
  restoreLastCheck,
  updateState,
  type GitHubRelease,
  type Release,
} from "./updates";

const SHA256 = "df5705f97384a3fd61d057e8a44a5b006000a42d324685f4e20fccc78e535023";

/** Steam's localStorage, which the tests run without. */
function memoryStorage() {
  const items = new Map<string, string>();
  return {
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => {
      items.set(key, value);
    },
    removeItem: (key: string) => {
      items.delete(key);
    },
  };
}

function gitHubRelease(tag: string, assets?: GitHubRelease["assets"]): GitHubRelease {
  return {
    tag_name: tag,
    html_url: `https://github.com/lexdrev/origami/releases/tag/${tag}`,
    assets: assets ?? [
      {
        name: "ORIGAMI.zip",
        browser_download_url: `https://github.com/lexdrev/origami/releases/download/${tag}/ORIGAMI.zip`,
        digest: `sha256:${SHA256}`,
      },
    ],
  };
}

describe("readRelease", () => {
  it("takes the version, the zip and its SHA-256", () => {
    expect(readRelease(gitHubRelease("v1.2.0"))).toEqual({
      version: "1.2.0",
      zipUrl: "https://github.com/lexdrev/origami/releases/download/v1.2.0/ORIGAMI.zip",
      sha256: SHA256,
      pageUrl: "https://github.com/lexdrev/origami/releases/tag/v1.2.0",
    });
  });

  it("refuses a release without the zip or its SHA-256", () => {
    expect(() => readRelease(gitHubRelease("v1.2.0", []))).toThrow("ORIGAMI.zip");
    const unchecked = { name: "ORIGAMI.zip", browser_download_url: "https://example.org/ORIGAMI.zip", digest: null };
    expect(() => readRelease(gitHubRelease("v1.2.0", [unchecked]))).toThrow("SHA-256");
  });

  it("refuses a tag that is not a version", () => {
    expect(() => readRelease(gitHubRelease("latest"))).toThrow("Unexpected release tag");
  });
});

describe("isNewer", () => {
  it("compares the numbers, not the text", () => {
    expect(isNewer("1.2.0", "1.1.0")).toBe(true);
    expect(isNewer("1.10.0", "1.9.0")).toBe(true);
    expect(isNewer("2.0.0", "1.99.99")).toBe(true);
    expect(isNewer("1.1.0", "1.1.0")).toBe(false);
    expect(isNewer("1.0.9", "1.1.0")).toBe(false);
  });

  it("puts a release after its betas", () => {
    expect(isNewer("1.2.0", "1.2.0-beta.1")).toBe(true);
    expect(isNewer("1.2.0-beta.1", "1.2.0")).toBe(false);
    expect(isNewer("1.2.0", "1.1.0-beta.1")).toBe(true);
  });
});

describe("checkForUpdates", () => {
  const answer = (body: unknown, status = 200) => {
    const fetch = vi.fn(() => Promise.resolve(new Response(JSON.stringify(body), { status })));
    vi.stubGlobal("fetch", fetch);
    return fetch;
  };

  beforeEach(() => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    vi.stubGlobal("localStorage", memoryStorage());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    updateState.set({ status: "idle" });
  });

  it("asks GitHub for the latest release and offers a newer one", async () => {
    const fetch = answer(gitHubRelease("v99.0.0"));
    const check = checkForUpdates();
    expect(updateState.get()).toEqual({ status: "checking" });
    await check;
    expect(fetch).toHaveBeenCalledWith(
      "https://api.github.com/repos/lexdrev/origami/releases/latest",
      expect.objectContaining({ headers: { Accept: "application/vnd.github+json" } }),
    );
    expect(updateState.get()).toMatchObject({ status: "available", release: { version: "99.0.0" } });
  });

  it("says this one is the latest when GitHub has the same", async () => {
    answer(gitHubRelease(`v${currentVersion}`));
    await checkForUpdates();
    expect(updateState.get()).toEqual({ status: "latest" });
  });

  it("says GitHub did not answer when the request fails", async () => {
    vi.stubGlobal("fetch", () => Promise.reject(new TypeError("Failed to fetch")));
    await checkForUpdates();
    expect(updateState.get()).toEqual({ status: "failed" });
  });

  it("says GitHub did not answer when it refuses, as past its hourly limit", async () => {
    answer({ message: "API rate limit exceeded" }, 403);
    await checkForUpdates();
    expect(updateState.get()).toEqual({ status: "failed" });
  });

  it("offers nothing from a release without its checked zip", async () => {
    answer(gitHubRelease("v99.0.0", []));
    await checkForUpdates();
    expect(updateState.get()).toEqual({ status: "failed" });
  });
});

describe("installUpdate", () => {
  const release: Release = {
    version: "1.2.0",
    zipUrl: "https://github.com/lexdrev/origami/releases/download/v1.2.0/ORIGAMI.zip",
    sha256: SHA256,
    pageUrl: "https://github.com/lexdrev/origami/releases/tag/v1.2.0",
  };

  beforeEach(() => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    updateState.set({ status: "available", release });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    updateState.set({ status: "idle" });
  });

  it("hands the zip and its SHA-256 to Decky as an update of ORIGAMI", async () => {
    const call = vi.fn(() => Promise.resolve(null));
    vi.stubGlobal("window", { DeckyBackend: { call } });
    await installUpdate(release);
    expect(call).toHaveBeenCalledWith("utilities/install_plugin", release.zipUrl, "ORIGAMI", "1.2.0", SHA256, 2);
    expect(updateState.get()).toEqual({ status: "available", release });
  });

  it("points to the release page when Decky does not take it", async () => {
    vi.stubGlobal("window", { DeckyBackend: { call: () => Promise.reject(new Error("no such route")) } });
    await installUpdate(release);
    expect(updateState.get()).toEqual({ status: "refused", release });
  });

  it("points to the release page without Decky's bus", async () => {
    vi.stubGlobal("window", {});
    await installUpdate(release);
    expect(updateState.get()).toEqual({ status: "refused", release });
  });
});

describe("the daily check", () => {
  const answer = (tag: string) => {
    const fetch = vi.fn(() => Promise.resolve(new Response(JSON.stringify(gitHubRelease(tag)))));
    vi.stubGlobal("fetch", fetch);
    return fetch;
  };

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-08T12:00:00Z"));
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    vi.stubGlobal("localStorage", memoryStorage());
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    updateState.set({ status: "idle" });
  });

  it("asks GitHub once a day", async () => {
    const fetch = answer("v99.0.0");

    await checkDaily();
    vi.setSystemTime(Date.now() + DAY_MS - 1000);
    await checkDaily();
    expect(fetch).toHaveBeenCalledTimes(1);

    vi.setSystemTime(Date.now() + 2000);
    await checkDaily();
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("asks again the next time ORIGAMI opens when GitHub did not answer", async () => {
    vi.stubGlobal("fetch", () => Promise.reject(new TypeError("Failed to fetch")));
    await checkDaily();
    expect(updateState.get()).toEqual({ status: "failed" });

    const fetch = answer(`v${currentVersion}`);
    await checkDaily();

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(updateState.get()).toEqual({ status: "latest" });
  });

  it("asks at once once the last answer is forgotten, as when switched off and on", async () => {
    const fetch = answer("v99.0.0");
    await checkDaily();

    forgetLastCheck();
    await checkDaily();

    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("offers after a Steam restart the newer release it found, without asking again", async () => {
    answer("v99.0.0");
    await checkDaily();
    updateState.set({ status: "idle" });

    restoreLastCheck();

    expect(updateState.get()).toMatchObject({ status: "available", release: { version: "99.0.0" } });
  });

  it("offers nothing after a restart once that release is installed", () => {
    // Found while an older ORIGAMI ran, then installed: it is the one running now.
    const installed = readRelease(gitHubRelease(`v${currentVersion}`));
    localStorage.setItem("origami.updates", JSON.stringify({ checkedAt: Date.now(), release: installed }));

    restoreLastCheck();

    expect(updateState.get()).toEqual({ status: "idle" });
  });
});
