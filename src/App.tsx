// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import type { ComponentType } from "react";

import { I18nProvider, resolveLanguage, useMessages } from "./i18n";
import { useCurrentScreen, type ScreenId } from "./navigation";
import { ChangesScreen } from "./screens/ChangesScreen";
import { MainScreen } from "./screens/MainScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { actionError, settings, steamLanguage } from "./state";
import { useStore } from "./store";
import { Alert } from "./ui/blocks";
import { styles } from "./ui/styles";

const screens: Record<ScreenId, ComponentType> = {
  main: MainScreen,
  settings: SettingsScreen,
  changes: ChangesScreen,
};

export function App() {
  const current = useStore(settings);
  const language = resolveLanguage(
    current.status === "ready" ? current.value.language : "auto",
    useStore(steamLanguage),
  );
  const CurrentScreen = screens[useCurrentScreen()];

  return (
    <I18nProvider language={language}>
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
