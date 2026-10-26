// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { useMessages } from "../i18n";
import { Alert, Screen, Tile } from "../ui/blocks";
import { DisplayIcon, FansIcon, GamepadIcon, PowerIcon } from "../ui/icons";
import { useTelemetry } from "../useTelemetry";
import { tileTexts } from "./tiles";

export function MainScreen() {
  const t = useMessages();
  const telemetry = useTelemetry();
  const tiles = tileTexts(telemetry.status === "ready" ? telemetry.value : null, t);

  return (
    <Screen>
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
