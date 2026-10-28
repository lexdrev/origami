// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import type { ComponentType } from "react";

import { I18nProvider, useMessages } from "./i18n";
import { useCurrentScreen, type ScreenId } from "./navigation";
import { ArmouryCrateScreen } from "./screens/ArmouryCrateScreen";
import { ChangesScreen } from "./screens/ChangesScreen";
import { CustomColourScreen } from "./screens/CustomColourScreen";
import { DisplayScreen } from "./screens/DisplayScreen";
import { GamepadScreen } from "./screens/GamepadScreen";
import { MainScreen } from "./screens/MainScreen";
import { PowerScreen } from "./screens/PowerScreen";
import { QamTabScreen } from "./screens/QamTabScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { actionError, useLanguage } from "./state";
import { useStore } from "./store";
import { Alert } from "./ui/blocks";
import { styles } from "./ui/styles";

const screens: Record<ScreenId, ComponentType> = {
  main: MainScreen,
  power: PowerScreen,
  display: DisplayScreen,
  customColour: CustomColourScreen,
  gamepad: GamepadScreen,
  armouryCrate: ArmouryCrateScreen,
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
