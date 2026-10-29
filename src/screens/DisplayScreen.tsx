// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { Focusable } from "@decky/ui";
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
import { Card, Header, Screen } from "../ui/blocks";
import { ChoiceGroup, filledTrack, Pressable, Slider } from "../ui/controls";
import { Rings } from "../ui/rings";
import { OwnedBy } from "./OwnedBy";

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

/** The screen saturation ORIGAMI writes to gamescope: the scale and its presets in one card. */
function SaturationSettings() {
  const t = useMessages();
  const value = useStore(saturation);
  if (value === null) return null;
  const preset = presetOf(value);

  return (
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
        track={filledTrack(value, 0, MAX_SATURATION)}
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
        custom={{
          label: t.display.presets.custom,
          detail: preset === undefined ? `${value}%` : "+",
          selected: preset === undefined,
        }}
      />
    </Card>
  );
}

/** One card: the switch in its head, then the mode, the colour, the speed and the brightness. */
function LightingSettings({ lighting }: { lighting: Lighting | null }) {
  const t = useMessages();
  // Until the lighting is first switched on, ORIGAMI leaves the rings to the controller.
  const change = (changes: Partial<Lighting>) =>
    void updateSettings({ lighting: { ...(lighting ?? DEFAULT_LIGHTING), ...changes } });
  const enabled = lighting?.enabled ?? false;

  return (
    <Card
      title={t.display.lighting}
      subtitle={lighting === null ? t.display.lightingUnset : enabled ? t.display.lightingOn : t.display.lightingOff}
      toggle={{
        value: enabled,
        action: t.actions.toggle,
        onChange: (on) => {
          change({ enabled: on });
        },
      }}
    >
      {lighting !== null && (
        <>
          <span className="og-card__label">{t.display.mode}</span>
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
          {usesColour(lighting.mode) && (
            <Colours
              lighting={lighting}
              onPick={(rgb) => {
                change({ left: rgb, right: rgb });
              }}
            />
          )}
          {hasSpeed(lighting.mode) && (
            <>
              <span className="og-card__label">{t.display.speed}</span>
              <ChoiceGroup
                label={t.display.speed}
                choices={LIGHT_SPEEDS.map((speed) => ({ value: speed, label: t.display.speeds[speed] }))}
                value={lighting.speed}
                action={t.actions.select}
                onChange={(speed) => {
                  change({ speed });
                }}
              />
            </>
          )}
          <span className="og-card__label">{t.display.brightness}</span>
          <ChoiceGroup
            label={t.display.brightness}
            choices={LIGHT_LEVELS.map((level) => ({ value: level, label: t.display.levels[level] }))}
            value={lighting.brightness}
            action={t.actions.select}
            onChange={(brightness) => {
              change({ brightness });
            }}
          />
        </>
      )}
    </Card>
  );
}

function Colours({ lighting, onPick }: { lighting: Lighting; onPick: (rgb: number) => void }) {
  const t = useMessages();
  const picked = paletteColour(lighting);
  const colours = lighting.left === lighting.right ? hex(lighting.left) : `${hex(lighting.left)} ${hex(lighting.right)}`;
  const name = picked ? t.display.colours[picked.id] : t.display.customColour;

  return (
    <>
      <div className="og-card__head">
        <span className="og-card__label">{t.display.colour}</span>
        <span className="og-card__aside">{`${name} · ${colours}`}</span>
      </div>
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
    </>
  );
}
