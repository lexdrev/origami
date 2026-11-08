// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import type { ReactNode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "../src/App";
import { watchBackendStart } from "../src/backendStart";
import { recordFanHistory } from "../src/fanHistory";
import { watchRunningGame } from "../src/games";
import { I18nProvider, type Language } from "../src/i18n";
import { ArmouryCrateScreen } from "../src/screens/ArmouryCrateScreen";
import { ChangesScreen } from "../src/screens/ChangesScreen";
import { DisplayScreen } from "../src/screens/DisplayScreen";
import { GamepadScreen } from "../src/screens/GamepadScreen";
import { MainScreen } from "../src/screens/MainScreen";
import { PowerScreen } from "../src/screens/PowerScreen";
import { QamTabScreen } from "../src/screens/QamTabScreen";
import { SettingsScreen } from "../src/screens/SettingsScreen";
import { PluginTitle } from "../src/PluginTitle";
import { loadAll } from "../src/state";
import { quickAccessColumn } from "../src/tabPosition";
import { styles } from "../src/ui/styles";

// Steam reports its interface language through SteamClient; the stand pretends to be Russian unless
// "?lang=english" says otherwise. Interface sounds go through Steam; the stand stays silent. Decky
// reports its version as 3.3.1, or as "?decky=v3.2.10" says.
const params = new URLSearchParams(location.search);
Object.assign(window, {
  SteamClient: { Settings: { GetCurrentLanguage: () => Promise.resolve(params.get("lang") ?? "russian") } },
  SteamUIStore: { GamepadUIAudio: { PlayNavSound: () => undefined } },
  DeckyBackend: { call: () => Promise.resolve({ current: params.get("decky") ?? "v3.3.1" }) },
});
// "?release=1.2.0" stands for the latest release on GitHub and "?release=none" for no answer; without
// it, "Check for updates" asks GitHub itself.
const release = params.get("release");
if (release !== null) {
  const page = `https://github.com/lexdrev/origami/releases/tag/v${release}`;
  window.fetch = () =>
    release === "none"
      ? Promise.reject(new TypeError("Failed to fetch"))
      : Promise.resolve(
          Response.json({
            tag_name: `v${release}`,
            html_url: page,
            assets: [{ name: "ORIGAMI.zip", browser_download_url: `${page}/ORIGAMI.zip`, digest: `sha256:${"0".repeat(64)}` }],
          }),
        );
}

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
        <Frame title="Power · RU">
          <Static language="ru">
            <PowerScreen />
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
        <Frame title="Armoury Crate · RU">
          <Static language="ru">
            <ArmouryCrateScreen />
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
watchBackendStart();
// "?game" in the address stands for a game Steam runs (mocks/decky-ui.tsx).
watchRunningGame();
recordFanHistory();
const container = document.getElementById("root");
if (container === null) throw new Error("No #root element");
createRoot(container).render(<Stand />);
