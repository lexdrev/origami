// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { version } from "../package.json";
import { callLoader, PLUGIN_NAME } from "./deckyLoader";
import { createStore } from "./store";

// ORIGAMI goes online only here: one request to GitHub for the latest release, when the user presses
// "Check", or once a day as ORIGAMI opens while the daily check is on. Decky does the update itself, as
// for the plugins of its store: it asks the user, downloads the zip, checks its SHA-256 and puts the new
// ORIGAMI in place of the old one.

const LATEST_RELEASE = "https://api.github.com/repos/lexdrev/origami/releases/latest";
/** Every release with its notes, the newest first: what a skipped version brought is there too. */
export const RELEASES_PAGE = "https://github.com/lexdrev/origami/releases";
const ZIP = "ORIGAMI.zip";
/** Decky's PluginInstallType.UPDATE: its prompt then speaks of an update. */
const INSTALL_AS_UPDATE = 2;
/** Long enough for a slow link; without one, as on a ship at sea, the check says so instead of spinning. */
export const CHECK_TIMEOUT_MS = 15_000;
const VERSION = /^\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?$/;
/** The daily check asks again once this much has passed since the last answer. */
export const DAY_MS = 24 * 60 * 60 * 1000;
/** Where Steam keeps the last answer between its restarts, so the marks of an update stay. */
const LAST_CHECK = "origami.updates";

/** The ORIGAMI that runs, from the package.json it was built with; the backend is not needed for it. */
export const currentVersion = version;

/** What ORIGAMI needs of a release: Decky downloads the zip and refuses one whose SHA-256 differs. */
export interface Release {
  version: string;
  zipUrl: string;
  sha256: string;
  pageUrl: string;
}

export type UpdateState =
  | { status: "idle" }
  | { status: "checking" }
  | { status: "latest" }
  | { status: "available"; release: Release }
  /** No answer from GitHub, or one without a release ORIGAMI can install. */
  | { status: "failed" }
  /** Decky did not take the update; the release page still has the zip. */
  | { status: "refused"; release: Release };

/** The last check, kept while ORIGAMI runs, so the settings show it again when they reopen. */
export const updateState = createStore<UpdateState>({ status: "idle" });

/** The newer release on offer, from a check just now or one remembered. */
export function offeredRelease(state: UpdateState): Release | null {
  return state.status === "available" || state.status === "refused" ? state.release : null;
}

interface LastCheck {
  checkedAt: number;
  /** The newer release GitHub had then; null when ORIGAMI was the latest. */
  release: Release | null;
}

function isRelease(value: unknown): value is Release {
  if (typeof value !== "object" || value === null) return false;
  const fields = value as Record<string, unknown>;
  return ["version", "zipUrl", "sha256", "pageUrl"].every((key) => typeof fields[key] === "string");
}

function readLastCheck(): LastCheck | null {
  const text = localStorage.getItem(LAST_CHECK);
  if (text === null) return null;
  const saved: unknown = JSON.parse(text);
  if (typeof saved !== "object" || saved === null) return null;
  const { checkedAt, release } = saved as Record<string, unknown>;
  if (typeof checkedAt !== "number" || (release !== null && !isRelease(release))) return null;
  return { checkedAt, release };
}

/** Forgets the last answer: the daily check, switched on again, asks at once. */
export function forgetLastCheck(): void {
  localStorage.removeItem(LAST_CHECK);
}

/** Offers again the newer release a check found before Steam restarted, unless it is installed by now. */
export function restoreLastCheck(): void {
  const release = readLastCheck()?.release ?? null;
  if (release !== null && isNewer(release.version, currentVersion)) updateState.set({ status: "available", release });
}

/** The daily check: once a day as ORIGAMI opens; without an answer it asks again the next time. */
export async function checkDaily(): Promise<void> {
  const last = readLastCheck();
  if (updateState.get().status === "checking" || (last !== null && Date.now() - last.checkedAt < DAY_MS)) return;
  await checkForUpdates();
}

/** The part of GitHub's answer ORIGAMI reads. */
export interface GitHubRelease {
  tag_name: string;
  html_url: string;
  assets: { name: string; browser_download_url: string; digest: string | null }[];
}

/** The release's version and its zip, with the SHA-256 GitHub computed when the zip was uploaded. */
export function readRelease(release: GitHubRelease): Release {
  const tagVersion = release.tag_name.replace(/^v/, "");
  if (!VERSION.test(tagVersion)) throw new Error(`Unexpected release tag ${release.tag_name}`);
  const zip = release.assets.find((asset) => asset.name === ZIP);
  const digest = zip?.digest ?? "";
  if (zip === undefined || !digest.startsWith("sha256:")) {
    throw new Error(`Release ${release.tag_name} has no ${ZIP} with a SHA-256`);
  }
  return {
    version: tagVersion,
    zipUrl: zip.browser_download_url,
    sha256: digest.slice("sha256:".length),
    pageUrl: release.html_url,
  };
}

/** Whether a version, such as "1.2.0", comes after another; a release comes after its betas ("1.2.0-beta.1"). */
export function isNewer(candidate: string, current: string): boolean {
  const [candidateCore = "", candidateBeta] = candidate.split("-", 2);
  const [currentCore = "", currentBeta] = current.split("-", 2);
  const a = candidateCore.split(".").map(Number);
  const b = currentCore.split(".").map(Number);
  for (let part = 0; part < 3; part++) {
    const difference = (a[part] ?? 0) - (b[part] ?? 0);
    if (difference !== 0) return difference > 0;
  }
  return currentBeta !== undefined && candidateBeta === undefined;
}

/** Asks GitHub for the latest release, which leaves out betas and drafts. */
export async function checkForUpdates(): Promise<void> {
  updateState.set({ status: "checking" });
  try {
    const response = await fetch(LATEST_RELEASE, {
      headers: { Accept: "application/vnd.github+json" },
      signal: AbortSignal.timeout(CHECK_TIMEOUT_MS),
    });
    if (!response.ok) throw new Error(`GitHub answered ${response.status}`);
    const release = readRelease((await response.json()) as GitHubRelease);
    const newer = isNewer(release.version, currentVersion);
    updateState.set(newer ? { status: "available", release } : { status: "latest" });
    const answer: LastCheck = { checkedAt: Date.now(), release: newer ? release : null };
    localStorage.setItem(LAST_CHECK, JSON.stringify(answer));
  } catch (error) {
    console.warn("ORIGAMI: cannot check for updates", error);
    updateState.set({ status: "failed" });
  }
}

/**
 * Hands the release to Decky, as its store does. Decky asks the user first; once they agree, it
 * removes this ORIGAMI (which gives the system back, keeping the settings) and starts the new one.
 */
export async function installUpdate(release: Release): Promise<void> {
  try {
    const { zipUrl, version: newVersion, sha256 } = release;
    await callLoader("utilities/install_plugin", zipUrl, PLUGIN_NAME, newVersion, sha256, INSTALL_AS_UPDATE);
  } catch (error) {
    console.warn("ORIGAMI: Decky did not take the update", error);
    updateState.set({ status: "refused", release });
  }
}
