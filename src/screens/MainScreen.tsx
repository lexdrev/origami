// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { Focusable } from "@decky/ui";
import { useEffect } from "react";

import { useMessages } from "../i18n";
import { navigate } from "../navigation";
import { steamTdpSlider } from "../power";
import { tileProblems } from "../problems";
import { ENTER_PREFERRED_CHILD } from "../quickAccess";
import { refreshSaturation, saturation } from "../saturation";
import {
  conflicts,
  gyro,
  heldPower,
  info,
  refreshConflicts,
  refreshGyro,
  refreshSound,
  refreshTriggerState,
  settings,
  soundState,
  triggerState,
} from "../state";
import { useStore } from "../store";
import { Alert, Screen, Tile } from "../ui/blocks";
import { IconButton } from "../ui/controls";
import { DisplayIcon, FansIcon, GamepadIcon, GearIcon, PowerIcon, SoundIcon } from "../ui/icons";
import { useTelemetry } from "../useTelemetry";
import { deviceName, systemName } from "./system";
import { offeredRelease, updateState } from "../updates";
import { tileTexts } from "./tiles";

export function MainScreen() {
  const t = useMessages();
  const telemetry = useTelemetry();
  const level = useStore(saturation);
  const current = useStore(settings);
  const held = useStore(heldPower);
  const owners = useStore(conflicts);
  const motors = useStore(triggerState);
  const axes = useStore(gyro);
  const plugin = useStore(info);
  const slider = useStore(steamTdpSlider) === true;
  const sound = useStore(soundState);
  const speakers = plugin.status === "ready" && plugin.value.sound;
  // Steam's own setting, changed from Steam's settings page too; other plugins and the controller
  // can change between visits as well.
  useEffect(() => {
    void refreshSaturation();
    void refreshConflicts();
    void refreshTriggerState();
    void refreshGyro();
  }, []);
  // Whether the crackle after sleep happens here, for the Sound tile's count.
  useEffect(() => {
    if (speakers) void refreshSound();
  }, [speakers]);
  const setting = current.status === "ready" ? current.value : null;
  const others = owners.status === "ready" ? owners.value : null;
  const ownTriggers = others?.triggers === null && motors.status === "ready" && motors.value === "available";
  const tiles = tileTexts(
    telemetry.status === "ready" ? telemetry.value : null,
    {
      saturation: level,
      vibration: setting && others?.vibration === null ? setting.vibration : undefined,
      tdp: held.status === "ready" ? (held.value.limits?.spl ?? null) : null,
      lighting: setting?.lighting && others?.lighting === null ? setting.lighting.enabled : undefined,
      triggers: setting && ownTriggers ? setting.triggerRumble : undefined,
      fanCurve: setting && others?.fans === null ? setting.fans : undefined,
      sound: setting && others?.sound === null ? setting.sound : undefined,
    },
    t,
  );
  // Each tile counts what its screen shows red; nothing while the settings or the owners are unknown.
  const problems =
    setting && others
      ? tileProblems({
          settings: setting,
          conflicts: others,
          gyro: axes.status === "ready" ? axes.value : null,
          triggers: motors.status === "ready" ? motors.value : null,
          buttons: plugin.status === "ready" ? plugin.value.buttons : null,
          steamTdpSlider: slider,
          contested: held.status === "ready" && held.value.contested,
          clockCrackle: sound.status === "ready" ? sound.value.clockFix : null,
        })
      : null;

  return (
    <Screen>
      <DeviceHeader />
      {telemetry.status === "failed" && <Alert title={t.errors.backend}>{telemetry.error}</Alert>}
      {/* Steam moves focus up and down a screen by default; the tiles go every way. Coming in from
          the quick access tabs, the focus lands on the Power tile beside them, not on the gear. */}
      <Focusable
        className="og-tiles"
        flow-children="grid"
        preferredFocus
        navEntryPreferPosition={ENTER_PREFERRED_CHILD}
      >
        <Tile
          icon={<PowerIcon />}
          name={t.main.tiles.power}
          preferredFocus
          {...tiles.power}
          problems={problems?.power}
          onOpen={() => {
            navigate("power");
          }}
        />
        <Tile
          icon={<FansIcon />}
          name={t.main.tiles.fans}
          {...tiles.fans}
          problems={problems?.fans}
          onOpen={() => {
            navigate("fans");
          }}
        />
        <Tile
          icon={<DisplayIcon />}
          name={t.main.tiles.display}
          {...tiles.display}
          problems={problems?.display}
          onOpen={() => {
            navigate("display");
          }}
        />
        <Tile
          icon={<GamepadIcon />}
          name={t.main.tiles.gamepad}
          {...tiles.gamepad}
          problems={problems?.gamepad}
          onOpen={() => {
            navigate("gamepad");
          }}
        />
        {/* Only the consoles whose speaker protection ORIGAMI has. */}
        {speakers && (
          <Tile
            icon={<SoundIcon />}
            name={t.main.tiles.sound}
            {...tiles.sound}
            problems={problems?.sound}
            onOpen={() => {
              navigate("sound");
            }}
          />
        )}
      </Focusable>
    </Screen>
  );
}

/** Under the title row: the console, its system and the way to the settings. */
function DeviceHeader() {
  const t = useMessages();
  const plugin = useStore(info);
  const current = useStore(settings);
  const update = useStore(updateState);
  const device = plugin.status === "ready" ? deviceName(plugin.value) : null;
  const system = plugin.status === "ready" ? systemName(plugin.value) : null;
  // What the daily update check found: marked here until it is installed or the check is switched off.
  const offered = current.status === "ready" && current.value.updateCheck ? offeredRelease(update) : null;

  return (
    <header className="og-header">
      <span className="og-header__titles">
        <span className="og-header__title">{device ?? t.unknown}</span>
        <span className="og-header__subtitle">{system ?? t.unknown}</span>
        {offered && <span className="og-header__update">{t.main.updateAvailable(offered.version)}</span>}
      </span>
      <IconButton
        label={t.main.settings}
        action={t.actions.open}
        onPress={() => {
          navigate("settings");
        }}
      >
        <GearIcon size={18} />
        {offered && <span className="og-icon-button__dot" aria-hidden="true" />}
      </IconButton>
    </header>
  );
}
