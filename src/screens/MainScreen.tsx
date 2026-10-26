// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { useMessages } from "../i18n";
import { navigate } from "../navigation";
import { info } from "../state";
import { useStore } from "../store";
import { Alert, Header, Screen, Tile } from "../ui/blocks";
import { IconButton } from "../ui/controls";
import { DisplayIcon, FansIcon, FoxMark, GamepadIcon, GearIcon, PowerIcon } from "../ui/icons";
import { useTelemetry } from "../useTelemetry";
import { deviceLine } from "./system";
import { tileTexts } from "./tiles";

export function MainScreen() {
  const t = useMessages();
  const plugin = useStore(info);
  const telemetry = useTelemetry();
  const tiles = tileTexts(telemetry.status === "ready" ? telemetry.value : null, t);

  return (
    <Screen>
      <Header
        brand
        icon={<FoxMark size={36} />}
        title="ORIGAMI"
        subtitle={plugin.status === "ready" ? deviceLine(plugin.value) : t.unknown}
        trailing={
          <IconButton
            label={t.main.settings}
            action={t.actions.open}
            onPress={() => {
              navigate("settings");
            }}
          >
            <GearIcon />
          </IconButton>
        }
      />
      {telemetry.status === "failed" && <Alert title={t.errors.backend}>{telemetry.error}</Alert>}
      <div className="og-tiles">
        <Tile icon={<PowerIcon />} name={t.main.tiles.power} {...tiles.power} />
        <Tile icon={<FansIcon />} name={t.main.tiles.fans} {...tiles.fans} />
        <Tile icon={<DisplayIcon />} name={t.main.tiles.display} {...tiles.display} />
        <Tile icon={<GamepadIcon />} name={t.main.tiles.gamepad} {...tiles.gamepad} />
      </div>
    </Screen>
  );
}
