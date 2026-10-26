// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import type { ReactNode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "../src/App";
import { I18nProvider, type Language } from "../src/i18n";
import { ChangesScreen } from "../src/screens/ChangesScreen";
import { MainScreen } from "../src/screens/MainScreen";
import { SettingsScreen } from "../src/screens/SettingsScreen";
import { loadAll } from "../src/state";
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

/** Decky's frame around an open plugin: its title row with the back button and the name, then the content. */
function DeckyPluginView({ children }: { children: ReactNode }) {
  return (
    <>
      <div className="decky-title">
        <span className="decky-back" aria-hidden="true">
          ←
        </span>
        <span>ORIGAMI</span>
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
        <Frame title="Settings · RU">
          <Static language="ru">
            <SettingsScreen />
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

void loadAll();
const container = document.getElementById("root");
if (container === null) throw new Error("No #root element");
createRoot(container).render(<Stand />);
