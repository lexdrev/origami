// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { Focusable } from "@decky/ui";
import { useEffect, useMemo, useRef, useState } from "react";

import type { Lighting } from "../backend";
import { useMessages } from "../i18n";
import { hex, hsToRgb, rgbToHs, type HueSaturation } from "../lighting";
import { back } from "../navigation";
import { UISound } from "../sounds";
import { previewLighting, settings, updateSettings } from "../state";
import { latestOnly, useStore } from "../store";
import { Card, Header, Screen } from "../ui/blocks";
import { ChoiceGroup, Pressable, Slider } from "../ui/controls";
import { Rings } from "../ui/rings";

type Target = "both" | "left" | "right";

const TARGETS: readonly Target[] = ["both", "left", "right"];
const HUE_TRACK = "linear-gradient(90deg, #f00, #ff0, #0f0, #0ff, #00f, #f0f, #f00)";
const STEP = 5;

export function CustomColourScreen() {
  const t = useMessages();
  const current = useStore(settings);
  const saved = current.status === "ready" ? current.value.lighting : null;

  // The palette opens this screen only while the lighting is on, so this is a passing state.
  if (saved === null) {
    return (
      <Screen onBack={back}>
        <Header onBack={back} title={t.customColour.title} subtitle={t.customColour.subtitle} />
      </Screen>
    );
  }
  return <CustomColourEditor saved={saved} />;
}

function CustomColourEditor({ saved }: { saved: Lighting }) {
  const t = useMessages();
  const [target, setTarget] = useState<Target>("both");
  const [colours, setColours] = useState(() => ({ left: rgbToHs(saved.left), right: rgbToHs(saved.right) }));
  const preview = useMemo(() => latestOnly(previewLighting), []);
  const finished = useRef(false);

  // Leaving any other way than Apply (B, the back button, the menu closing) puts the saved colours back.
  useEffect(
    () => () => {
      if (!finished.current) preview.send(saved);
    },
    [preview, saved],
  );

  const lighting: Lighting = { ...saved, left: hsToRgb(colours.left), right: hsToRgb(colours.right) };
  const edited = target === "right" ? colours.right : colours.left;

  const update = (changes: Partial<HueSaturation>) => {
    const value = { ...edited, ...changes };
    const next = {
      left: target === "right" ? colours.left : value,
      right: target === "left" ? colours.right : value,
    };
    setColours(next);
    preview.send({ ...saved, left: hsToRgb(next.left), right: hsToRgb(next.right) });
  };
  const cancel = () => {
    finished.current = true;
    preview.send(saved);
    back();
  };
  const apply = () => {
    finished.current = true;
    preview.drop();
    void updateSettings({ lighting });
    back();
  };

  return (
    <Screen onBack={cancel}>
      <Header onBack={cancel} title={t.customColour.title} subtitle={t.customColour.subtitle} />
      <ChoiceGroup
        label={t.customColour.title}
        choices={TARGETS.map((value) => ({ value, label: t.customColour.targets[value] }))}
        value={target}
        action={t.actions.select}
        onChange={setTarget}
      />
      <Card>
        {/* The colour itself, steady and bright; the rings on the console show the chosen mode. */}
        <Rings
          lighting={{ ...lighting, mode: "static", brightness: "high" }}
          editing={{ left: target !== "right", right: target !== "left" }}
        />
        <div className="og-colour-value">
          <span className="og-colour-value__swatch" style={{ background: hex(hsToRgb(edited)) }} />
          <span className="og-colour-value__hex">{hex(hsToRgb(edited))}</span>
        </div>
      </Card>
      <Card title={t.customColour.hue} aside={<span className="og-card__aside--accent">{`${edited.hue}°`}</span>}>
        <Slider
          label={t.customColour.hue}
          value={edited.hue}
          min={0}
          max={359}
          step={STEP}
          wrap
          track={HUE_TRACK}
          thumb={hex(hsToRgb({ hue: edited.hue, saturation: 100 }))}
          lessLabel={t.actions.less}
          moreLabel={t.actions.more}
          onChange={(hue) => {
            update({ hue });
          }}
        />
      </Card>
      <Card
        title={t.customColour.saturation}
        aside={<span className="og-card__aside--accent">{`${edited.saturation}%`}</span>}
      >
        <Slider
          label={t.customColour.saturation}
          value={edited.saturation}
          min={0}
          max={100}
          step={STEP}
          track={`linear-gradient(90deg, #ffffff, ${hex(hsToRgb({ hue: edited.hue, saturation: 100 }))})`}
          thumb={hex(hsToRgb(edited))}
          lessLabel={t.actions.less}
          moreLabel={t.actions.more}
          onChange={(saturation) => {
            update({ saturation });
          }}
        />
        <div className="og-slider__ends" aria-hidden="true">
          <span>{t.customColour.white}</span>
          <span>{t.customColour.pure}</span>
        </div>
      </Card>
      <p className="og-note">{t.customColour.hint}</p>
      <Focusable className="og-actions" flow-children="row">
        <Pressable className="og-button" action={t.customColour.cancel} onPress={cancel}>
          {t.customColour.cancel}
        </Pressable>
        <Pressable
          className="og-button og-button--primary"
          action={t.customColour.apply}
          sound={UISound.Press}
          onPress={apply}
        >
          {t.customColour.apply}
        </Pressable>
      </Focusable>
    </Screen>
  );
}
