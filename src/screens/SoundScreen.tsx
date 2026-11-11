// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { useEffect } from "react";

import type { Settings, Sound, SoundState } from "../backend";
import { runningPlugins } from "../deckyPlugins";
import { chooseOwnSound, profileOf, withSound, type Game } from "../gameProfiles";
import { openedProfile, runningGame } from "../games";
import { useMessages } from "../i18n";
import { back, navigate } from "../navigation";
import { unset } from "../problems";
import { SOUND_VOLUMES, SOUND_WIDTHS, UNSET_SOUND, soundOwner, soundStatus } from "../sound";
import {
  conflicts,
  refreshConflicts,
  refreshSound,
  setGameSound,
  setSound,
  settings,
  soundState,
  updateSettings,
} from "../state";
import { useStore } from "../store";
import { usePoll } from "../usePoll";
import { Card, Header, Screen, SwitchLine } from "../ui/blocks";
import { ChoiceGroup, NavRow, ToggleRow } from "../ui/controls";
import { LoadFailed } from "./LoadFailed";
import { OwnedBy } from "./OwnedBy";

/** As often as the backend itself looks whether the speakers play and the filter runs. */
const POLL_INTERVAL_MS = 2000;

/** The Sound screen: the running game's own sound switch on top, or the way to the games' sounds while none runs. */
export function SoundScreen() {
  const t = useMessages();
  return <SoundView title={t.sound.title} game={useStore(runningGame)} />;
}

/** A game's sound opened from the list: the Sound screen as it is while that game runs. */
export function GameSoundScreen() {
  const t = useMessages();
  const game = useStore(openedProfile);
  const running = useStore(runningGame);
  if (game === null) return <SoundView title={t.sound.title} game={null} />;
  return (
    <SoundView
      title={game.name}
      subtitle={running?.appId === game.appId ? undefined : t.power.profileSub}
      game={game}
    />
  );
}

interface SoundViewProps {
  title: string;
  subtitle?: string | undefined;
  game: Game | null;
}

function SoundView({ title, subtitle, game }: SoundViewProps) {
  const t = useMessages();
  const current = useStore(settings);
  const owners = useStore(conflicts);
  const state = useStore(soundState);
  const running = useStore(runningGame);

  useEffect(() => {
    void refreshConflicts();
  }, []);
  // Headphones come and go while the screen is open.
  usePoll(refreshSound, POLL_INTERVAL_MS);

  const sound = state.status === "ready" ? state.value : null;
  const owner = owners.status === "ready" ? soundOwner(owners.value.sound, sound, runningPlugins()) : null;
  // The clock fix is the console's, not a game's: a profile opened from the list leaves it out.
  const elsewhere = game !== null && running?.appId !== game.appId;
  return (
    <Screen onBack={back}>
      <Header onBack={back} title={title} subtitle={subtitle} />
      <LoadFailed loads={[current, owners]} />
      {current.status === "ready" &&
        owners.status === "ready" &&
        (owner !== null ? (
          <OwnedBy
            title={t.sound.ownedBy(owner.name)}
            text={owner.plugin ? t.sound.ownedText(owner.name) : t.sound.filterOwnedText(owner.name)}
            decky={owner.inDecky}
          />
        ) : (
          <OwnSound setting={current.value} game={game} running={running} state={sound} />
        ))}
      {current.status === "ready" && sound?.clockFix === true && !elsewhere && (
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

interface OwnSoundProps {
  setting: Settings;
  /** The game whose sound switch is on top; null for the general sound and the way to the games' sounds. */
  game: Game | null;
  running: Game | null;
  state: SoundState | null;
}

/**
 * The profile row and the card. With a game, the card sets its own sound while it has an active
 * profile, else the general one.
 */
function OwnSound({ setting, game, running, state }: OwnSoundProps) {
  const t = useMessages();
  const profile = game === null ? undefined : profileOf(setting.gameSound, game.appId);
  const own = profile?.active === true;
  const shown = (profile !== undefined && own ? profile.sound : setting.sound) ?? UNSET_SOUND;
  // The filter's state belongs to what applies now: the running game's own sound while it has an
  // active profile, else the general one.
  const runningProfile = running === null ? undefined : profileOf(setting.gameSound, running.appId);
  const appliedGame = runningProfile?.active === true ? runningProfile.appId : null;
  const applied = appliedGame === (own ? game?.appId : null);
  const save = (next: Sound) => {
    if (game !== null && own) setGameSound(withSound(setting.gameSound, game.appId, next));
    else setSound(next);
  };
  return (
    <>
      {game === null ? (
        <NavRow
          title={t.power.profiles}
          count={setting.gameSound.length}
          subtitle={t.power.profilesSub}
          action={t.actions.open}
          onPress={() => {
            navigate("gameSounds");
          }}
        />
      ) : (
        <GameSoundRow setting={setting} game={game} own={own} />
      )}
      <SoundCard sound={shown} state={applied ? state : null} onChange={save} />
    </>
  );
}

/**
 * The game's own sound, switched on and off like its own power. Nothing is made until it is
 * switched on: the first time copies the general sound, and switched off, the profile is kept for
 * the next time.
 */
function GameSoundRow({ setting, game, own }: { setting: Settings; game: Game; own: boolean }) {
  const t = useMessages();
  const kept = profileOf(setting.gameSound, game.appId) !== undefined;
  return (
    <ToggleRow
      title={t.sound.gameSound}
      subtitle={own ? t.power.gameProfileOn(game.name) : t.power.gameProfileOff(game.name)}
      {...(!own && kept ? { note: t.power.gameProfileKept } : {})}
      value={own}
      action={t.actions.toggle}
      onChange={(on) => {
        setGameSound(chooseOwnSound(setting.gameSound, game, setting.sound ?? UNSET_SOUND, on));
      }}
    />
  );
}

interface SoundCardProps {
  sound: Sound;
  /** The filter's state while this sound is the one that applies; null otherwise and until read. */
  state: SoundState | null;
  onChange: (sound: Sound) => void;
}

/** The switch in the head, and while it is on the volume, the width and the voices. */
function SoundCard({ sound, state, onChange }: SoundCardProps) {
  const t = useMessages();
  const change = (changes: Partial<Sound>) => {
    onChange({ ...sound, ...changes });
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
