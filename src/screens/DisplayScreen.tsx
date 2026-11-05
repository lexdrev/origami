// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { Focusable } from "@decky/ui";
import { useEffect } from "react";

import type { Lighting } from "../backend";
import { useMessages } from "../i18n";
import {
  BRIGHTNESS,
  DEFAULT_LIGHTING,
  hasLevels,
  hasSpeed,
  hex,
  LIGHT_LEVELS,
  levelOf,
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
  presetOf,
  refreshSaturation,
  saturation,
  SATURATION_STEP,
  saturationScale,
  setSaturation,
} from "../saturation";
import { UISound } from "../sounds";
import { conflicts, info, refreshConflicts, setLighting, settings } from "../state";
import { useStore } from "../store";
import { Card, Header, Screen } from "../ui/blocks";
import { ChoiceGroup, filledTrack, Pressable, Slider } from "../ui/controls";
import { Rings } from "../ui/rings";
import { LoadFailed } from "./LoadFailed";
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
        <LoadFailed loads={[owners]} />
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
      <LoadFailed loads={[current]} />
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

/**
 * The screen saturation ORIGAMI writes to gamescope: the scale and its presets in one card. 100% is
 * what the system shows by itself; on SteamOS that is the top, so the scale only goes down from it.
 */
function SaturationSettings() {
  const t = useMessages();
  const value = useStore(saturation);
  const plugin = useStore(info);
  if (value === null) return null;
  const scale = saturationScale(plugin.status === "ready" ? plugin.value.versions.os.id : null);
  const shown = Math.min(value, scale.max);
  const preset = presetOf(shown, scale.presets);
  const set = (percent: number) => {
    setSaturation(percent, scale.max);
  };

  return (
    <Card
      title={t.display.saturation}
      subtitle={scale.steamos ? `${t.display.saturationSub} · ${t.display.saturationSteamOs}` : t.display.saturationSub}
      aside={<span className="og-card__value">{`${shown}%`}</span>}
    >
      <Slider
        label={t.display.saturation}
        value={shown}
        min={0}
        max={scale.max}
        step={SATURATION_STEP}
        track={filledTrack(shown, 0, scale.max)}
        thumb="var(--og-accent)"
        notch={DEFAULT_SATURATION}
        lessLabel={t.actions.less}
        moreLabel={t.actions.more}
        onChange={set}
      />
      <div className="og-slider__ends" aria-hidden="true">
        <span>0</span>
        <span>{scale.max / 2}</span>
        <span>{scale.max}</span>
      </div>
      <ChoiceGroup
        label={t.display.saturation}
        choices={scale.presets.map((choice) => ({
          value: choice.id,
          label: t.display.presets[choice.id],
          detail: `${choice.value}%`,
        }))}
        value={preset?.id}
        action={t.actions.select}
        onChange={(id) => {
          set(scale.presets.find((choice) => choice.id === id)?.value ?? DEFAULT_SATURATION);
        }}
        custom={{
          label: t.display.presets.custom,
          detail: preset === undefined ? `${shown}%` : "+",
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
  const change = (changes: Partial<Lighting>) => {
    setLighting({ ...(lighting ?? DEFAULT_LIGHTING), ...changes });
  };
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
          <Brightness
            lighting={lighting}
            onChange={(brightness) => {
              change({ brightness });
            }}
          />
        </>
      )}
    </Card>
  );
}

/**
 * One slider for every mode: 5–100% for ORIGAMI's colours; rainbow and spiral, which only the
 * controller's three levels dim, stop at three places named under it.
 */
function Brightness({ lighting, onChange }: { lighting: Lighting; onChange: (brightness: number) => void }) {
  const t = useMessages();
  const { brightness } = lighting;

  if (hasLevels(lighting.mode)) {
    const level = levelOf(brightness);
    const top = LIGHT_LEVELS.length - 1;
    return (
      <>
        <span className="og-card__label">{t.display.brightness}</span>
        {/* Above the slider: below the card's last stop Steam's scrolling never gets there. */}
        <span className="og-card__hint">{t.display.brightnessSteps}</span>
        <Slider
          label={t.display.brightness}
          value={level}
          min={0}
          max={top}
          step={1}
          track={filledTrack(level, 0, top)}
          thumb="var(--og-accent)"
          notch={1}
          lessLabel={t.actions.less}
          moreLabel={t.actions.more}
          onChange={(index) => {
            onChange(LIGHT_LEVELS[index]?.brightness ?? BRIGHTNESS.max);
          }}
        />
        <div className="og-slider__ends" aria-hidden="true">
          {LIGHT_LEVELS.map((step, index) => (
            <span key={step.id} className={index === level ? "og-slider__end--on" : undefined}>
              {t.display.levels[step.id]}
            </span>
          ))}
        </div>
      </>
    );
  }
  return (
    <>
      <div className="og-card__head">
        <span className="og-card__label">{t.display.brightness}</span>
        <span className="og-card__value">{`${brightness}%`}</span>
      </div>
      <Slider
        label={t.display.brightness}
        value={brightness}
        min={BRIGHTNESS.min}
        max={BRIGHTNESS.max}
        step={BRIGHTNESS.step}
        track={filledTrack(brightness, BRIGHTNESS.min, BRIGHTNESS.max)}
        thumb="var(--og-accent)"
        lessLabel={t.actions.less}
        moreLabel={t.actions.more}
        onChange={onChange}
      />
      <div className="og-slider__ends" aria-hidden="true">
        <span>{`${BRIGHTNESS.min}%`}</span>
        <span>{`${BRIGHTNESS.max}%`}</span>
      </div>
    </>
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
