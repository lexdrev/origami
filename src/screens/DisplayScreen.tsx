// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { Focusable, Navigation } from "@decky/ui";
import { useEffect } from "react";

import type { Lighting } from "../backend";
import { useMessages } from "../i18n";
import {
  DEFAULT_LIGHTING,
  hasSpeed,
  hex,
  LIGHT_LEVELS,
  LIGHT_MODES,
  LIGHT_SPEEDS,
  PALETTE,
  paletteColour,
  SPECTRUM_SWATCH,
  usesColour,
} from "../lighting";
import { back, navigate } from "../navigation";
import { UISound } from "../sounds";
import { conflicts, refreshConflicts, settings, updateSettings } from "../state";
import { useStore } from "../store";
import { Alert, Card, Header, Screen, SectionLabel } from "../ui/blocks";
import { ChoiceGroup, Pressable, ToggleRow } from "../ui/controls";
import { Rings } from "../ui/rings";

/** Decky's own list of plugins, where one can be switched off or removed. */
const DECKY_PLUGINS_ROUTE = "/decky/settings/plugins";

export function DisplayScreen() {
  const t = useMessages();
  const current = useStore(settings);
  const owners = useStore(conflicts);

  useEffect(() => {
    void refreshConflicts();
  }, []);

  const owner = owners.status === "ready" ? owners.value.lighting : null;
  return (
    <Screen onBack={back}>
      <Header onBack={back} title={t.display.title} />
      {owner !== null && <LightingOwnedBy plugin={owner} />}
      {owner === null && owners.status === "ready" && current.status === "ready" && (
        <LightingSettings lighting={current.value.lighting} />
      )}
    </Screen>
  );
}

function LightingOwnedBy({ plugin }: { plugin: string }) {
  const t = useMessages();
  return (
    <>
      <SectionLabel>{t.display.lighting}</SectionLabel>
      <Alert title={t.display.ownedBy(plugin)}>{t.display.ownedText(plugin)}</Alert>
      <Pressable
        className="og-button"
        action={t.actions.open}
        sound={UISound.Press}
        onPress={() => {
          Navigation.Navigate(DECKY_PLUGINS_ROUTE);
          Navigation.CloseSideMenus();
        }}
      >
        {t.display.openPlugins}
      </Pressable>
    </>
  );
}

function LightingSettings({ lighting }: { lighting: Lighting | null }) {
  const t = useMessages();
  // Until the lighting is first switched on, ORIGAMI leaves the rings to the controller.
  const change = (changes: Partial<Lighting>) =>
    void updateSettings({ lighting: { ...(lighting ?? DEFAULT_LIGHTING), ...changes } });
  const enabled = lighting?.enabled ?? false;

  return (
    <>
      <ToggleRow
        title={t.display.lighting}
        subtitle={enabled ? t.display.lightingOn : t.display.lightingOff}
        value={enabled}
        action={t.actions.toggle}
        onChange={(on) => {
          change({ enabled: on });
        }}
      />
      {lighting?.enabled && (
        <>
          <Card title={t.display.mode}>
            <Rings lighting={lighting} />
            <ChoiceGroup
              label={t.display.mode}
              choices={LIGHT_MODES.map((mode) => ({ value: mode, label: t.display.modes[mode] }))}
              value={lighting.mode}
              action={t.actions.select}
              onChange={(mode) => {
                change({ mode });
              }}
            />
          </Card>
          {usesColour(lighting.mode) && (
            <Colours
              lighting={lighting}
              onPick={(rgb) => {
                change({ left: rgb, right: rgb });
              }}
            />
          )}
          {hasSpeed(lighting.mode) && (
            <Card title={t.display.speed}>
              <ChoiceGroup
                label={t.display.speed}
                choices={LIGHT_SPEEDS.map((speed) => ({ value: speed, label: t.display.speeds[speed] }))}
                value={lighting.speed}
                action={t.actions.select}
                onChange={(speed) => {
                  change({ speed });
                }}
              />
            </Card>
          )}
          <Card title={t.display.brightness}>
            <ChoiceGroup
              label={t.display.brightness}
              choices={LIGHT_LEVELS.map((level) => ({ value: level, label: t.display.levels[level] }))}
              value={lighting.brightness}
              action={t.actions.select}
              onChange={(brightness) => {
                change({ brightness });
              }}
            />
          </Card>
        </>
      )}
    </>
  );
}

function Colours({ lighting, onPick }: { lighting: Lighting; onPick: (rgb: number) => void }) {
  const t = useMessages();
  const picked = paletteColour(lighting);
  const colours = lighting.left === lighting.right ? hex(lighting.left) : `${hex(lighting.left)} ${hex(lighting.right)}`;
  const name = picked ? t.display.colours[picked.id] : t.display.customColour;

  return (
    <Card title={t.display.colour} aside={`${name} · ${colours}`}>
      <Focusable className="og-swatches" flow-children="row" role="group" aria-label={t.display.colour}>
        {PALETTE.map((colour) => (
          <Pressable
            key={colour.id}
            className={colour === picked ? "og-swatch og-swatch--selected" : "og-swatch"}
            style={{ background: hex(colour.rgb) }}
            label={t.display.colours[colour.id]}
            pressed={colour === picked}
            action={t.actions.select}
            sound={UISound.Press}
            onPress={() => {
              onPick(colour.rgb);
            }}
          />
        ))}
        <Pressable
          className={picked === null ? "og-swatch og-swatch--selected" : "og-swatch"}
          style={{ background: SPECTRUM_SWATCH }}
          label={t.display.customColour}
          pressed={picked === null}
          action={t.actions.open}
          onPress={() => {
            navigate("customColour");
          }}
        />
      </Focusable>
    </Card>
  );
}
