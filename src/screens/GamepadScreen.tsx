// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { useEffect, useState } from "react";

import type { Vibration } from "../backend";
import { useMessages } from "../i18n";
import { back, navigate } from "../navigation";
import { UISound } from "../sounds";
import {
  conflicts,
  refreshConflicts,
  refreshTelemetry,
  setVibration,
  settings,
  telemetry,
  testVibration,
  updateSettings,
} from "../state";
import { useStore } from "../store";
import { Card, Header, Improvement, Screen } from "../ui/blocks";
import { ChoiceGroup, filledTrack, NavRow, Pressable, Slider, ToggleRow } from "../ui/controls";
import { PlayIcon } from "../ui/icons";
import {
  currentVibration,
  FACTORY_VIBRATION,
  formatVibration,
  MAX_VIBRATION,
  presetOf,
  together,
  tooStrong,
  VIBRATION_PRESETS,
  VIBRATION_STEP,
} from "../vibration";
import { armouryCrateSummary } from "./armouryCrate";
import { OwnedBy } from "./OwnedBy";

export function GamepadScreen() {
  const t = useMessages();
  const current = useStore(settings);
  const owners = useStore(conflicts);

  useEffect(() => {
    void refreshConflicts();
    // What the driver holds, shown until ORIGAMI sets its own strength.
    void refreshTelemetry();
  }, []);

  if (current.status !== "ready" || owners.status !== "ready") {
    return (
      <Screen onBack={back}>
        <Header onBack={back} title={t.gamepad.title} />
      </Screen>
    );
  }
  const vibrationOwner = owners.value.vibration;
  const buttonSummary = armouryCrateSummary(current.value.armouryCrate, current.value.armouryCrateHold, t);
  return (
    <Screen onBack={back}>
      <Header onBack={back} title={t.gamepad.title} />
      {vibrationOwner === null ? (
        <VibrationSettings setting={current.value.vibration} />
      ) : (
        <OwnedBy
          section={t.gamepad.vibration}
          title={t.gamepad.vibrationOwnedBy(vibrationOwner)}
          text={t.gamepad.vibrationOwnedText(vibrationOwner)}
        />
      )}
      <ToggleRow
        title={t.gamepad.qamAssist}
        subtitle={current.value.qamAssist ? t.gamepad.qamAssistOn : t.gamepad.qamAssistOff}
        problem={!current.value.qamAssist}
        value={current.value.qamAssist}
        action={t.actions.toggle}
        onChange={(qamAssist) => void updateSettings({ qamAssist })}
      />
      <NavRow
        title={t.gamepad.armouryCrate}
        subtitle={buttonSummary ?? t.gamepad.armouryCrateUnassigned}
        problem={buttonSummary === null}
        action={t.actions.open}
        onPress={() => {
          navigate("armouryCrate");
        }}
      />
    </Screen>
  );
}

function VibrationSettings({ setting }: { setting: Vibration | null }) {
  const t = useMessages();
  const readings = useStore(telemetry);
  const vibration = currentVibration(setting, readings.status === "ready" ? readings.value : null) ?? FACTORY_VIBRATION;
  const [separate, setSeparate] = useState(vibration.left !== vibration.right);
  const preset = separate ? undefined : presetOf(vibration);

  return (
    <>
      <Card
        title={t.gamepad.vibration}
        aside={<span className="og-card__value">{formatVibration(vibration)}</span>}
      >
        {tooStrong(vibration) && <Improvement>{t.gamepad.tooStrong}</Improvement>}
        {separate ? (
          <>
            <StrengthSlider
              caption={t.gamepad.left}
              value={vibration.left}
              onChange={(left) => {
                setVibration({ ...vibration, left });
              }}
            />
            <StrengthSlider
              caption={t.gamepad.right}
              value={vibration.right}
              onChange={(right) => {
                setVibration({ ...vibration, right });
              }}
            />
          </>
        ) : (
          <StrengthSlider
            value={vibration.left}
            onChange={(strength) => {
              setVibration({ left: strength, right: strength });
            }}
          />
        )}
        <ChoiceGroup
          label={t.gamepad.handles}
          choices={[
            { value: "together", label: t.gamepad.together },
            { value: "separate", label: t.gamepad.separate },
          ]}
          value={separate ? "separate" : "together"}
          action={t.actions.select}
          onChange={(choice) => {
            if (choice === "together" && vibration.left !== vibration.right) setVibration(together(vibration));
            setSeparate(choice === "separate");
          }}
          after={
            <Pressable
              className="og-choice og-choice--action"
              action={t.gamepad.test}
              sound={UISound.Press}
              onPress={() => void testVibration()}
            >
              <PlayIcon />
              {t.gamepad.test}
            </Pressable>
          }
        />
      </Card>
      <ChoiceGroup
        label={t.gamepad.vibration}
        choices={VIBRATION_PRESETS.map((choice) => ({
          value: choice.id,
          label: t.gamepad.presets[choice.id],
          detail: `${choice.value}%`,
        }))}
        value={preset?.id}
        action={t.actions.select}
        onChange={(id) => {
          const strength = VIBRATION_PRESETS.find((choice) => choice.id === id)?.value ?? MAX_VIBRATION;
          setSeparate(false);
          setVibration({ left: strength, right: strength });
        }}
      />
    </>
  );
}

interface StrengthSliderProps {
  /** Names the handle when each has its own slider. */
  caption?: string;
  value: number;
  onChange: (value: number) => void;
}

function StrengthSlider({ caption, value, onChange }: StrengthSliderProps) {
  const t = useMessages();
  return (
    <Slider
      label={caption ?? t.gamepad.vibration}
      caption={caption}
      value={value}
      min={0}
      max={MAX_VIBRATION}
      step={VIBRATION_STEP}
      track={filledTrack(value, 0, MAX_VIBRATION)}
      thumb="var(--og-accent)"
      lessLabel={t.actions.less}
      moreLabel={t.actions.more}
      onChange={onChange}
    />
  );
}
