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
import {
  DEFAULT_SATURATION,
  MAX_SATURATION,
  presetOf,
  refreshSaturation,
  saturation,
  SATURATION_PRESETS,
  SATURATION_STEP,
  setSaturation,
} from "../saturation";
import { UISound } from "../sounds";
import { conflicts, refreshConflicts, settings, updateSettings } from "../state";
import { useStore } from "../store";
import { Alert, Card, Header, Screen, SectionLabel } from "../ui/blocks";
import { ChoiceGroup, choiceClass, Pressable, Slider, ToggleRow } from "../ui/controls";
import { Rings } from "../ui/rings";

/** Decky's own list of plugins, where one can be switched off or removed. */
const DECKY_PLUGINS_ROUTE = "/decky/settings/plugins";

export function DisplayScreen() {
  const t = useMessages();
  const current = useStore(settings);
  const owners = useStore(conflicts);

  useEffect(() => {
    void refreshConflicts();
    void refreshSaturation();
  }, []);

  if (owners.status !== "ready") {
    return (
      <Screen onBack={back}>
        <Header onBack={back} title={t.display.title} />
      </Screen>
    );
  }
  const { saturation: saturationOwner, lighting: lightingOwner } = owners.value;
  return (
    <Screen onBack={back}>
      <Header onBack={back} title={t.display.title} />
      {saturationOwner === null ? (
        <SaturationSettings />
      ) : (
        <OwnedBy
          section={t.display.saturation}
          title={t.display.saturationOwnedBy(saturationOwner)}
          text={t.display.saturationOwnedText(saturationOwner)}
        />
      )}
      {lightingOwner === null ? (
        current.status === "ready" && <LightingSettings lighting={current.value.lighting} />
      ) : (
        <OwnedBy
          section={t.display.lighting}
          title={t.display.ownedBy(lightingOwner)}
          text={t.display.ownedText(lightingOwner)}
        />
      )}
    </Screen>
  );
}

/** A section another plugin drives: why ORIGAMI stays out, and the way to that plugin. */
function OwnedBy({ section, title, text }: { section: string; title: string; text: string }) {
  const t = useMessages();
  return (
    <>
      <SectionLabel>{section}</SectionLabel>
      <Alert title={title}>{text}</Alert>
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

/** Steam's own colour vibrance, shown where Steam has colour management. */
function SaturationSettings() {
  const t = useMessages();
  const value = useStore(saturation);
  if (value === null) return null;
  const preset = presetOf(value);
  const fill = `${(value / MAX_SATURATION) * 100}%`;

  return (
    <>
      <Card
        title={t.display.saturation}
        subtitle={t.display.saturationSub}
        aside={<span className="og-card__value">{`${value}%`}</span>}
      >
        <Slider
          label={t.display.saturation}
          value={value}
          min={0}
          max={MAX_SATURATION}
          step={SATURATION_STEP}
          track={`linear-gradient(90deg, var(--og-accent) ${fill}, var(--og-track) ${fill})`}
          thumb="var(--og-accent)"
          notch={DEFAULT_SATURATION}
          lessLabel={t.actions.less}
          moreLabel={t.actions.more}
          onChange={setSaturation}
        />
        <div className="og-slider__ends" aria-hidden="true">
          <span>0</span>
          <span>{DEFAULT_SATURATION}</span>
          <span>{MAX_SATURATION}</span>
        </div>
      </Card>
      <ChoiceGroup
        label={t.display.saturation}
        choices={SATURATION_PRESETS.map((choice) => ({
          value: choice.id,
          label: t.display.presets[choice.id],
          detail: `${choice.value}%`,
        }))}
        value={preset?.id}
        action={t.actions.select}
        onChange={(id) => {
          setSaturation(SATURATION_PRESETS.find((choice) => choice.id === id)?.value ?? DEFAULT_SATURATION);
        }}
        after={
          <span className={`${choiceClass(preset === undefined, true)} og-choice--static`}>
            {t.display.presets.custom}
            <span className="og-choice__detail">{preset === undefined ? `${value}%` : "+"}</span>
          </span>
        }
      />
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
