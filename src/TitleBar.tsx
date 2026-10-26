// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { I18nProvider, useMessages } from "./i18n";
import { navigate, useCurrentScreen } from "./navigation";
import { deviceLine } from "./screens/system";
import { info, useLanguage } from "./state";
import { useStore } from "./store";
import { IconButton } from "./ui/controls";
import { FoxMark, GearIcon } from "./ui/icons";

/**
 * Plugin part of the Decky title row, right after Decky's own back button.
 * It renders outside the plugin content, so it sets up the language itself.
 */
export function TitleBar() {
  return (
    <I18nProvider language={useLanguage()}>
      <Title />
    </I18nProvider>
  );
}

function Title() {
  const t = useMessages();
  const plugin = useStore(info);
  const onMainScreen = useCurrentScreen() === "main";

  return (
    <div className="og-title">
      <span className="og-title__icon">
        <FoxMark size={22} />
      </span>
      <span className="og-title__texts">
        <span className="og-title__name">ORIGAMI</span>
        <span className="og-title__sub">{plugin.status === "ready" ? deviceLine(plugin.value) : t.unknown}</span>
      </span>
      {onMainScreen && (
        <IconButton
          label={t.main.settings}
          action={t.actions.open}
          onPress={() => {
            navigate("settings");
          }}
        >
          <GearIcon size={16} />
        </IconButton>
      )}
    </div>
  );
}
