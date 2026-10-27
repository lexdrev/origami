// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { useEffect, useState } from "react";

import type { TriggerRumble, Vibration } from "../backend";
import { useMessages } from "../i18n";
import { back, navigate } from "../navigation";
import { UISound } from "../sounds";
import {
  conflicts,
  gyro,
  refreshConflicts,
  refreshGyro,
  refreshTelemetry,
  refreshTriggerState,
  setTriggerRumble,
  setVibration,
  settings,
  telemetry,
  testTriggerRumble,
  testVibration,
  triggerState,
  updateSettings,
} from "../state";
import { useStore } from "../store";
import { currentTriggerRumble, separateTriggerOwner, TRIGGER_CHOICES, TRIGGER_LEVELS } from "../triggers";
import { Alert, Card, Header, Screen } from "../ui/blocks";
import { ChoiceGroup, filledTrack, NavRow, Pressable, Slider, ToggleRow } from "../ui/controls";
import { PlayIcon } from "../ui/icons";
import {
  currentVibration,
  customDetail,
  FACTORY_VIBRATION,
  formatVibration,
  MAX_VIBRATION,
  presetOf,
  silent,
  together,
  VIBRATION_NOTCH,
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
    void refreshGyro();
    void refreshTriggerState();
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
  const triggerOwner = separateTriggerOwner(owners.value);
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
      {owners.value.triggers === null ? (
        <TriggerRumbleSettings setting={current.value.triggerRumble} />
      ) : (
        triggerOwner !== null && (
          <OwnedBy
            section={t.gamepad.triggers}
            title={t.gamepad.triggersOwnedBy(triggerOwner)}
            text={t.gamepad.triggersOwnedText(triggerOwner)}
          />
        )
      )}
      <ToggleRow
        title={t.gamepad.qamAssist}
        subtitle={current.value.qamAssist ? t.gamepad.qamAssistOn : t.gamepad.qamAssistOff}
        problem={!current.value.qamAssist}
        value={current.value.qamAssist}
        action={t.actions.toggle}
        onChange={(qamAssist) => void updateSettings({ qamAssist })}
      />
      <GyroFix enabled={current.value.gyroFix} />
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

/** One card: the switch in its head, then the scale, the handles with the test and the presets. */
function VibrationSettings({ setting }: { setting: Vibration | null }) {
  const t = useMessages();
  const readings = useStore(telemetry);
  const vibration = currentVibration(setting, readings.status === "ready" ? readings.value : null) ?? FACTORY_VIBRATION;
  const [separate, setSeparate] = useState(vibration.left !== vibration.right);
  const preset = separate ? undefined : presetOf(vibration);

  return (
    <Card
      title={t.gamepad.vibration}
      subtitle={vibration.enabled ? t.gamepad.vibrationOn : t.gamepad.vibrationStill}
      problem={!vibration.enabled}
      toggle={{
        value: vibration.enabled,
        action: t.actions.toggle,
        onChange: (enabled) => {
          setVibration({ ...vibration, enabled });
        },
      }}
    >
      <div className="og-card__head">
        <span className="og-card__label">{t.gamepad.strength}</span>
        <span className="og-card__value">{formatVibration(vibration, t.gamepad.off)}</span>
      </div>
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
            setVibration({ ...vibration, left: strength, right: strength });
          }}
        />
      )}
      <div className={separate ? "og-slider__ends og-slider__ends--captioned" : "og-slider__ends"} aria-hidden="true">
        <span>0</span>
        <span>{VIBRATION_NOTCH}</span>
        <span>{MAX_VIBRATION}</span>
      </div>
      <ChoiceGroup
        label={t.gamepad.handles}
        choices={[
          { value: "together", label: t.gamepad.together },
          { value: "separate", label: t.gamepad.separate },
        ]}
        value={separate ? "separate" : "together"}
        action={t.actions.select}
        onChange={(choice) => {
          if (choice === "together") setVibration(together(vibration));
          setSeparate(choice === "separate");
        }}
        after={<TestButton disabled={silent(vibration)} onPress={() => void testVibration()} />}
      />
      <ChoiceGroup
        label={t.gamepad.strength}
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
          setVibration({ enabled: true, left: strength, right: strength });
        }}
        custom={{
          label: t.gamepad.presets.custom,
          detail: customDetail(vibration, preset),
          selected: preset === undefined,
        }}
      />
    </Card>
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
      notch={VIBRATION_NOTCH}
      lessLabel={t.actions.less}
      moreLabel={t.actions.more}
      onChange={onChange}
    />
  );
}

/** A second of the motors, beside the choices of a vibration card. */
function TestButton({ disabled = false, onPress }: { disabled?: boolean; onPress: () => void }) {
  const t = useMessages();
  return (
    <Pressable
      className="og-choice og-choice--action"
      action={t.gamepad.test}
      sound={UISound.Press}
      disabled={disabled}
      onPress={onPress}
    >
      <PlayIcon />
      {t.gamepad.test}
    </Pressable>
  );
}

/** Shown only on consoles with trigger motors; off, they stay still, which is the problem (as QAM assist). */
function TriggerRumbleSettings({ setting }: { setting: TriggerRumble | null }) {
  const t = useMessages();
  const state = useStore(triggerState);
  if (state.status !== "ready" || state.value === "unavailable") return null;
  const rumble = currentTriggerRumble(setting);

  return (
    <Card
      title={t.gamepad.triggers}
      subtitle={rumble.enabled ? t.gamepad.triggersOn : t.gamepad.triggersStill}
      problem={!rumble.enabled}
      toggle={{
        value: rumble.enabled,
        action: t.actions.toggle,
        onChange: (enabled) => {
          setTriggerRumble({ ...rumble, enabled });
        },
      }}
    >
      <ChoiceGroup
        label={t.gamepad.triggers}
        choices={TRIGGER_CHOICES.map((triggers) => ({ value: triggers, label: t.gamepad.triggerChoices[triggers] }))}
        value={rumble.triggers}
        action={t.actions.select}
        onChange={(triggers) => {
          setTriggerRumble({ ...rumble, triggers });
        }}
        after={<TestButton onPress={() => void testTriggerRumble()} />}
      />
      <ChoiceGroup
        label={t.gamepad.triggerStrength}
        choices={TRIGGER_LEVELS.map((level) => ({
          value: level.id,
          label: t.gamepad.triggerLevels[level.id],
          detail: `${level.value}%`,
        }))}
        value={rumble.level}
        action={t.actions.select}
        onChange={(level) => {
          setTriggerRumble({ ...rumble, level });
        }}
      />
      <span className="og-choices__note">{t.gamepad.triggerStrengthNote}</span>
    </Card>
  );
}

/** Shown only where ORIGAMI knows the axes are wrong: on other devices and fixed systems there is nothing to do. */
function GyroFix({ enabled }: { enabled: boolean }) {
  const t = useMessages();
  const state = useStore(gyro);
  if (state.status !== "ready") return null;
  switch (state.value) {
    case "foreign":
      return <Alert title={t.gamepad.gyroForeign}>{t.gamepad.gyroForeignText}</Alert>;
    case "wrong":
    case "fixed":
    case "outdated":
      return (
        <ToggleRow
          title={t.gamepad.gyroFix}
          subtitle={enabled ? t.gamepad.gyroFixOn : t.gamepad.gyroFixOff}
          problem={!enabled}
          note={t.gamepad.gyroFixRestart}
          value={enabled}
          action={t.actions.toggle}
          onChange={(gyroFix) => {
            // InputPlumber restarts to take the new axes; the screen then shows what it took.
            void updateSettings({ gyroFix }).then(refreshGyro);
          }}
        />
      );
    case "unavailable":
    case "fixed_in_system":
      return null;
  }
}
