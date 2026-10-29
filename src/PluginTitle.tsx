// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { FoxMark } from "./ui/icons";

/**
 * The fox and the plugin name for Steam's title row, in Steam's own title font: at the top of
 * ORIGAMI's tab and after the back button in Decky's row.
 */
export function PluginTitle() {
  return (
    <span className="og-plugin-title">
      <span className="og-plugin-title__icon">
        <FoxMark size={28} />
      </span>
      ORIGAMI
    </span>
  );
}
