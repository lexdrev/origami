// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { useEffect, useState } from "react";

import type { TriggerRumble, Vibration } from "../backend";
import { useMessages } from "../i18n";
import { back, navigate } from "../navigation";
import { buttonUnset, gyroProblem, unset } from "../problems";
import { UISound } from "../sounds";
import {
  conflicts,
  gyro,
  refreshConflicts,
  refreshGyro,
  refreshTriggerState,
  setTriggerRumble,
  setVibration,
  settings,
  testTriggerRumble,
  testVibration,
  triggerState,
  updateSettings,
} from "../state";
import { useStore } from "../store";
import {
  currentTriggerRumble,
  separateTriggerOwner,
  TRIGGER_CHOICES,
  TRIGGER_LEVELS,
  TRIGGER_PATTERNS,
} from "../triggers";
import { Alert, Card, Header, Screen } from "../ui/blocks";
import { ChoiceGroup, filledTrack, NavRow, Pressable, Slider, ToggleRow } from "../ui/controls";
import { PlayIcon } from "../ui/icons";
import {
  customDetail,
  DEFAULT_VIBRATION,
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
  const { armouryCrate, armouryCrateHold } = current.value;
  const buttonSummary = armouryCrateSummary(armouryCrate ?? "none", armouryCrateHold ?? "none", t);
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
        problem={unset(current.value.qamAssist)}
        value={current.value.qamAssist ?? false}
        action={t.actions.toggle}
        onChange={(qamAssist) => void updateSettings({ qamAssist })}
      />
      <GyroFix fix={current.value.gyroFix} />
      <NavRow
        title={t.gamepad.armouryCrate}
        subtitle={buttonSummary ?? t.gamepad.armouryCrateUnassigned}
        problem={buttonUnset(armouryCrate, armouryCrateHold)}
        action={t.actions.open}
        onPress={() => {
          navigate("armouryCrate");
        }}
      />
    </Screen>
  );
}

/** One card: the switch in its head, the handles with the test, then the strength: scale and presets. */
function VibrationSettings({ setting }: { setting: Vibration | null }) {
  const t = useMessages();
  // Never set, after "restore everything" for one, the controller keeps its own strength. That is
  // not on ORIGAMI's scale, as games rumble it without ORIGAMI's lift, so the card shows none.
  const vibration = setting ?? DEFAULT_VIBRATION;
  const enabled = setting?.enabled ?? false;
  const [separate, setSeparate] = useState(vibration.left !== vibration.right);
  const preset = separate ? undefined : presetOf(vibration);
  const state = enabled ? t.gamepad.vibrationOn : t.gamepad.vibrationStill;

  return (
    <Card
      title={t.gamepad.vibration}
      subtitle={setting === null ? t.gamepad.vibrationUnset : state}
      toggle={{
        value: enabled,
        action: t.actions.toggle,
        onChange: (enabled) => {
          setVibration({ ...vibration, enabled });
        },
      }}
    >
      <span className="og-card__label">{t.gamepad.handles}</span>
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

/** Shown only on consoles with trigger motors; they stay still, a problem until the user chooses (as QAM assist). */
function TriggerRumbleSettings({ setting }: { setting: TriggerRumble | null }) {
  const t = useMessages();
  const state = useStore(triggerState);
  if (state.status !== "ready" || state.value === "unavailable") return null;
  const rumble = currentTriggerRumble(setting);

  return (
    <Card
      title={t.gamepad.triggers}
      subtitle={rumble.enabled ? t.gamepad.triggersOn : t.gamepad.triggersStill}
      problem={unset(setting)}
      toggle={{
        value: rumble.enabled,
        action: t.actions.toggle,
        onChange: (enabled) => {
          setTriggerRumble({ ...rumble, enabled });
        },
      }}
    >
      <span className="og-card__label">{t.gamepad.triggerSides}</span>
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
      <span className="og-card__label">{t.gamepad.triggerCharacter}</span>
      <ChoiceGroup
        label={t.gamepad.triggerPattern}
        choices={TRIGGER_PATTERNS.map((pattern) => ({ value: pattern, label: t.gamepad.triggerPatterns[pattern] }))}
        value={rumble.taps ? "taps" : "steady"}
        action={t.actions.select}
        onChange={(pattern) => {
          setTriggerRumble({ ...rumble, taps: pattern === "taps" });
        }}
      />
      <span className="og-card__label">{t.gamepad.strength}</span>
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
function GyroFix({ fix }: { fix: boolean | null }) {
  const t = useMessages();
  const state = useStore(gyro);
  if (state.status !== "ready") return null;
  const enabled = fix ?? false;
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
          problem={gyroProblem(state.value, fix)}
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
