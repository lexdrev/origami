// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import type { ReactNode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "../src/App";
import { I18nProvider, type Language } from "../src/i18n";
import { ChangesScreen } from "../src/screens/ChangesScreen";
import { DisplayScreen } from "../src/screens/DisplayScreen";
import { GamepadScreen } from "../src/screens/GamepadScreen";
import { MainScreen } from "../src/screens/MainScreen";
import { QamTabScreen } from "../src/screens/QamTabScreen";
import { SettingsScreen } from "../src/screens/SettingsScreen";
import { PluginTitle } from "../src/PluginTitle";
import { loadAll } from "../src/state";
import { quickAccessColumn } from "../src/tabPosition";
import { styles } from "../src/ui/styles";

// Steam reports its interface language through SteamClient; the stand pretends to be Russian.
// Interface sounds go through Steam; the stand stays silent.
Object.assign(window, {
  SteamClient: { Settings: { GetCurrentLanguage: () => Promise.resolve("russian") } },
  SteamUIStore: { GamepadUIAudio: { PlayNavSound: () => undefined } },
});

function Frame({ title, children }: { title: string; children: ReactNode }) {
  return (
    <figure className="frame">
      <figcaption>{title}</figcaption>
      <div className="panel">{children}</div>
    </figure>
  );
}

/** Decky's frame around an open plugin: its title row with the back button and ORIGAMI's title, then the content. */
function DeckyPluginView({ children }: { children: ReactNode }) {
  return (
    <>
      <div className="decky-title">
        <span className="decky-back" aria-hidden="true">
          ←
        </span>
        <PluginTitle />
      </div>
      <div className="decky-content">{children}</div>
    </>
  );
}

function Static({ language, children }: { language: Language; children: ReactNode }) {
  return (
    <I18nProvider language={language}>
      <div className="decky-content">
        <div className="og-root">{children}</div>
      </div>
    </I18nProvider>
  );
}

function Stand() {
  return (
    <>
      <style>{styles}</style>
      <main className="frames">
        <Frame title="Interactive (Tab, Enter, Esc)">
          <DeckyPluginView>
            <App />
          </DeckyPluginView>
        </Frame>
        <Frame title="Main · EN">
          <Static language="en">
            <MainScreen />
          </Static>
        </Frame>
        <Frame title="Display & Light · RU">
          <Static language="ru">
            <DisplayScreen />
          </Static>
        </Frame>
        <Frame title="Gamepad · RU">
          <Static language="ru">
            <GamepadScreen />
          </Static>
        </Frame>
        <Frame title="Settings · RU">
          <Static language="ru">
            <SettingsScreen />
          </Static>
        </Frame>
        <Frame title="Quick access tab · RU">
          <Static language="ru">
            <QamTabScreen />
          </Static>
        </Frame>
        <Frame title="System changes · RU">
          <Static language="ru">
            <ChangesScreen />
          </Static>
        </Frame>
      </main>
    </>
  );
}

// The quick access column as on the console: Notifications, Friends, Quick settings, Performance,
// Soundtracks, Help, Decky.
quickAccessColumn.set({
  tabs: [0, 3, 4, 5, 7, 6, 999].map((key) => ({ key, title: null })),
  arranger: null,
});
void loadAll();
const container = document.getElementById("root");
if (container === null) throw new Error("No #root element");
createRoot(container).render(<Stand />);
