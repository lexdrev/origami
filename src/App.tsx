// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import type { ComponentType } from "react";

import { I18nProvider, useMessages } from "./i18n";
import { useCurrentScreen, type ScreenId } from "./navigation";
import { ChangesScreen } from "./screens/ChangesScreen";
import { MainScreen } from "./screens/MainScreen";
import { QamTabScreen } from "./screens/QamTabScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { actionError, useLanguage } from "./state";
import { useStore } from "./store";
import { Alert } from "./ui/blocks";
import { styles } from "./ui/styles";

const screens: Record<ScreenId, ComponentType> = {
  main: MainScreen,
  settings: SettingsScreen,
  qamTab: QamTabScreen,
  changes: ChangesScreen,
};

export function App() {
  const CurrentScreen = screens[useCurrentScreen()];

  return (
    <I18nProvider language={useLanguage()}>
      {/* The style element renders inside the quick access window, which is a separate document. */}
      <style>{styles}</style>
      <div className="og-root">
        <ActionError />
        <CurrentScreen />
      </div>
    </I18nProvider>
  );
}

function ActionError() {
  const t = useMessages();
  const error = useStore(actionError);
  return error === null ? null : <Alert title={t.errors.backend}>{error}</Alert>;
}
