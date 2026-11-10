// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { useEffect } from "react";

import type { Sound, SoundState } from "../backend";
import { useMessages } from "../i18n";
import { back } from "../navigation";
import { unset } from "../problems";
import { DEFAULT_SOUND, SOUND_VOLUMES, SOUND_WIDTHS, soundStatus } from "../sound";
import {
  conflicts,
  refreshConflicts,
  refreshSound,
  setSound,
  settings,
  soundState,
  updateSettings,
} from "../state";
import { useStore } from "../store";
import { usePoll } from "../usePoll";
import { Card, Header, Screen, SwitchLine } from "../ui/blocks";
import { ChoiceGroup, ToggleRow } from "../ui/controls";
import { LoadFailed } from "./LoadFailed";
import { OwnedBy } from "./OwnedBy";

/** As often as the backend itself looks whether the speakers play and the filter runs. */
const POLL_INTERVAL_MS = 2000;

export function SoundScreen() {
  const t = useMessages();
  const current = useStore(settings);
  const owners = useStore(conflicts);
  const state = useStore(soundState);

  useEffect(() => {
    void refreshConflicts();
  }, []);
  // Headphones come and go while the screen is open.
  usePoll(refreshSound, POLL_INTERVAL_MS);

  const owner = owners.status === "ready" ? owners.value.sound : null;
  const sound = state.status === "ready" ? state.value : null;
  return (
    <Screen onBack={back}>
      <Header onBack={back} title={t.sound.title} />
      <LoadFailed loads={[current, owners]} />
      {current.status === "ready" &&
        owners.status === "ready" &&
        (owner !== null ? (
          <OwnedBy title={t.sound.ownedBy(owner)} text={t.sound.ownedText(owner)} />
        ) : (
          <SoundCard setting={current.value.sound} state={sound} />
        ))}
      {current.status === "ready" && sound?.clockFix === true && (
        <ToggleRow
          title={t.sound.clockFix}
          subtitle={current.value.clockFix ? t.sound.clockFixOn : t.sound.clockFixOff}
          problem={unset(current.value.clockFix)}
          note={t.sound.clockFixWhy}
          value={current.value.clockFix ?? false}
          action={t.actions.toggle}
          onChange={(clockFix) => void updateSettings({ clockFix })}
        />
      )}
    </Screen>
  );
}

/** The switch in the head, and while it is on the volume, the width and the voices. */
function SoundCard({ setting, state }: { setting: Sound | null; state: SoundState | null }) {
  const t = useMessages();
  const sound = setting ?? { ...DEFAULT_SOUND, enabled: false };
  const change = (changes: Partial<Sound>) => {
    setSound({ ...sound, ...changes });
  };
  const subtitle = sound.enabled ? t.sound[soundStatus(state)] : t.sound.off;
  return (
    <Card
      title={t.sound.card}
      subtitle={subtitle}
      toggle={{
        value: sound.enabled,
        action: t.actions.toggle,
        onChange: (enabled) => {
          change({ enabled });
        },
      }}
    >
      <span className="og-card__label">{t.sound.volume}</span>
      <span className="og-card__hint">{t.sound.volumeNote}</span>
      <ChoiceGroup
        label={t.sound.volume}
        choices={SOUND_VOLUMES.map((volume) => ({ value: String(volume), label: t.sound.volumes[volume] }))}
        value={String(sound.volumeDb)}
        action={t.actions.select}
        onChange={(value) => {
          const volumeDb = SOUND_VOLUMES.find((volume) => String(volume) === value);
          if (volumeDb !== undefined) change({ volumeDb });
        }}
      />
      <span className="og-card__label">{t.sound.width}</span>
      <span className="og-card__hint">{t.sound.widthNote}</span>
      <ChoiceGroup
        label={t.sound.width}
        choices={SOUND_WIDTHS.map((width) => ({ value: width, label: t.sound.widths[width] }))}
        value={sound.width}
        action={t.actions.select}
        onChange={(width) => {
          change({ width });
        }}
      />
      <span className="og-card__divider" aria-hidden="true" />
      <SwitchLine
        title={t.sound.voices}
        subtitle={t.sound.voicesSub}
        value={sound.voices}
        action={t.actions.toggle}
        onChange={(voices) => {
          change({ voices });
        }}
      />
    </Card>
  );
}
