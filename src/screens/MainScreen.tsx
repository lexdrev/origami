// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { Focusable } from "@decky/ui";
import { useEffect } from "react";

import { useMessages } from "../i18n";
import { navigate } from "../navigation";
import { refreshSaturation, saturation } from "../saturation";
import { info } from "../state";
import { useStore } from "../store";
import { Alert, Screen, Tile } from "../ui/blocks";
import { IconButton } from "../ui/controls";
import { DisplayIcon, FansIcon, GamepadIcon, GearIcon, PowerIcon } from "../ui/icons";
import { useTelemetry } from "../useTelemetry";
import { deviceName, systemName } from "./system";
import { tileTexts } from "./tiles";

export function MainScreen() {
  const t = useMessages();
  const telemetry = useTelemetry();
  const level = useStore(saturation);
  // Steam's own setting, changed from Steam's settings page too.
  useEffect(() => {
    void refreshSaturation();
  }, []);
  const tiles = tileTexts(telemetry.status === "ready" ? telemetry.value : null, level, t);

  return (
    <Screen>
      <DeviceHeader />
      {telemetry.status === "failed" && <Alert title={t.errors.backend}>{telemetry.error}</Alert>}
      {/* Steam moves focus up and down a screen by default; the tiles go every way. */}
      <Focusable className="og-tiles" flow-children="grid">
        <Tile icon={<PowerIcon />} name={t.main.tiles.power} {...tiles.power} />
        <Tile icon={<FansIcon />} name={t.main.tiles.fans} {...tiles.fans} />
        <Tile
          icon={<DisplayIcon />}
          name={t.main.tiles.display}
          {...tiles.display}
          onOpen={() => {
            navigate("display");
          }}
        />
        <Tile
          icon={<GamepadIcon />}
          name={t.main.tiles.gamepad}
          {...tiles.gamepad}
          onOpen={() => {
            navigate("gamepad");
          }}
        />
      </Focusable>
    </Screen>
  );
}

/** Under the title row: the console, its system and the way to the settings. */
function DeviceHeader() {
  const t = useMessages();
  const plugin = useStore(info);
  const device = plugin.status === "ready" ? deviceName(plugin.value) : null;
  const system = plugin.status === "ready" ? systemName(plugin.value) : null;

  return (
    <header className="og-header">
      <span className="og-header__titles">
        <span className="og-header__title">{device ?? t.unknown}</span>
        <span className="og-header__subtitle">{system ?? t.unknown}</span>
      </span>
      <IconButton
        label={t.main.settings}
        action={t.actions.open}
        onPress={() => {
          navigate("settings");
        }}
      >
        <GearIcon size={18} />
      </IconButton>
    </header>
  );
}
