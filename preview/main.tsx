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
Object.assign(window, {
  SteamClient: { Settings: { GetCurrentLanguage: () => Promise.resolve("russian") } },
});

function Frame({ title, children }: { title: string; children: ReactNode }) {
  return (
    <figure className="frame">
      <figcaption>{title}</figcaption>
      <div className="panel">{children}</div>
    </figure>
  );
}

function Static({ language, children }: { language: Language; children: ReactNode }) {
  return (
    <I18nProvider language={language}>
      <div className="og-root">{children}</div>
    </I18nProvider>
  );
}

function Stand() {
  return (
    <>
      <style>{styles}</style>
      <main className="frames">
        <Frame title="Interactive (Tab, Enter, Esc)">
          <App />
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
