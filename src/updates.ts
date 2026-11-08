// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { version } from "../package.json";
import { callLoader, PLUGIN_NAME } from "./deckyLoader";
import { createStore } from "./store";

// ORIGAMI goes online only here, when the user presses "Check for updates": one request to GitHub
// for the latest release. Decky does the update itself, as for the plugins of its store: it asks the
// user, downloads the zip, checks its SHA-256 and puts the new ORIGAMI in place of the old one.

const LATEST_RELEASE = "https://api.github.com/repos/lexdrev/origami/releases/latest";
const ZIP = "ORIGAMI.zip";
/** Decky's PluginInstallType.UPDATE: its prompt then speaks of an update. */
const INSTALL_AS_UPDATE = 2;
/** Long enough for a slow link; without one, as on a ship at sea, the check says so instead of spinning. */
export const CHECK_TIMEOUT_MS = 15_000;
const VERSION = /^\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?$/;

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
