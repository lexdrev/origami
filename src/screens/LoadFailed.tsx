// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { useMessages } from "../i18n";
import type { Loadable } from "../store";
import { Alert } from "../ui/blocks";

/**
 * Why a screen shows nothing yet: the backend's error for the first of its data that failed to
 * load. Opening the plugin again loads it again (reloadFailed).
 */
export function LoadFailed({ loads }: { loads: readonly Loadable<unknown>[] }) {
  const t = useMessages();
  const failed = loads.find((load) => load.status === "failed");
  return failed?.status === "failed" ? <Alert title={t.errors.backend}>{failed.error}</Alert> : null;
}
