// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { useEffect } from "react";

import type { Settings, Sharpness, SharpnessGameState, SharpnessState } from "../backend";
import { chooseOwnSharpness, profileOf, withSharpness, type Game } from "../gameProfiles";
import { openedProfile, runningGame } from "../games";
import { useMessages } from "../i18n";
import { back, navigate } from "../navigation";
import { markRead } from "../notices";
import {
  DEFAULT_SHARPNESS,
  MAX_SHARPNESS,
  SHARPNESS_PRESETS,
  SHARPNESS_STEP,
  UNSET_SHARPNESS,
  sharpnessPresetOf,
  sharpnessStatus,
  takenNotice,
} from "../sharpness";
import {
  conflicts,
  refreshConflicts,
  refreshSharpness,
  setGameSharpness,
  setSharpness,
  settings,
  sharpnessState,
} from "../state";
import { useStore } from "../store";
import { usePoll } from "../usePoll";
import { Card, Header, Screen } from "../ui/blocks";
import { ChoiceGroup, NavRow, Slider, ToggleRow, filledTrack } from "../ui/controls";
import { LoadFailed } from "./LoadFailed";
import { OwnedBy } from "./OwnedBy";

/** Games start and end while the screen is open, and a started game loads the layer a moment later. */
const POLL_INTERVAL_MS = 2000;

/** The Service screen: the running game's own sharpness switch on top, or the way to the games' profiles. */
export function ServiceScreen() {
  const t = useMessages();
  return <ServiceView title={t.service.title} game={useStore(runningGame)} />;
}

/** A game's sharpness opened from the list: the screen as it is while that game runs. */
export function SharpnessProfileScreen() {
  const t = useMessages();
  const game = useStore(openedProfile);
  const running = useStore(runningGame);
  if (game === null) return <ServiceView title={t.service.title} game={null} />;
  return (
    <ServiceView
      title={game.name}
      subtitle={running?.appId === game.appId ? undefined : t.power.profileSub}
      game={game}
    />
  );
}

interface ServiceViewProps {
  title: string;
  subtitle?: string | undefined;
  game: Game | null;
}

function ServiceView({ title, subtitle, game }: ServiceViewProps) {
  const t = useMessages();
  const current = useStore(settings);
  const owners = useStore(conflicts);
  const state = useStore(sharpnessState);
  const running = useStore(runningGame);

  useEffect(() => {
    void refreshConflicts();
  }, []);
  usePoll(refreshSharpness, POLL_INTERVAL_MS);

  const owner = owners.status === "ready" ? owners.value.sharpness : null;
  const now = state.status === "ready" ? state.value : null;
  // The running game's launch options keep the sharpness: on this game's screen there is nothing to set.
  const taken = now?.game === "managed" && game !== null && running?.appId === game.appId ? now : null;
  return (
    <Screen onBack={back}>
      <Header onBack={back} title={title} subtitle={subtitle} />
      <LoadFailed loads={[current, owners]} />
      {current.status === "ready" &&
        owners.status === "ready" &&
        (owner !== null ? (
          <OwnedBy
            section={t.service.sharpness}
            title={t.service.ownedBy(owner)}
            text={t.service.ownedText(owner)}
          />
        ) : taken !== null && game !== null ? (
          <LaunchOwned state={taken} game={game} />
        ) : (
          <OwnSharpness setting={current.value} game={game} running={running} state={now?.game ?? null} />
        ))}
    </Screen>
  );
}

/**
 * The running game is started through a wrapper that builds its chain of graphics layers itself, or
 * its launch options set the sharpening layer: the sharpness in it is theirs, and ORIGAMI says whose.
 */
function LaunchOwned({ state, game }: { state: SharpnessState; game: Game }) {
  const t = useMessages();
  const { owner, sharpening, companion } = state;
  // The main screen counts this block until it has been shown once.
  useEffect(() => {
    markRead(takenNotice(owner));
  }, [owner]);
  if (owner === null) {
    return (
      <OwnedBy
        section={t.service.sharpness}
        title={t.service.launchOwned}
        text={t.service.launchText(game.name)}
        advice={companion === null ? undefined : t.service.companionText(companion)}
        decky={false}
      />
    );
  }
  const own = (sharpening === null ? undefined : t.service.launcherSharpening[sharpening]) ?? t.service.launcherOwn;
  return (
    <OwnedBy
      section={t.service.sharpness}
      title={t.service.launcherOwnedBy(owner)}
      text={`${t.service.launcherText(game.name)} ${own}`}
      advice={companion === null ? undefined : t.service.launcherAdvice(companion)}
    />
  );
}

interface OwnSharpnessProps {
  setting: Settings;
  /** The game whose switch is on top; null for the general sharpness and the way to the games' profiles. */
  game: Game | null;
  running: Game | null;
  state: SharpnessGameState | null;
}

/**
 * The profile row and the card. With a game, the card sets its own sharpness while it has an
 * active profile, else the general one.
 */
function OwnSharpness({ setting, game, running, state }: OwnSharpnessProps) {
  const t = useMessages();
  const profile = game === null ? undefined : profileOf(setting.gameSharpness, game.appId);
  const own = profile?.active === true;
  const shown = (profile !== undefined && own ? profile.sharpness : setting.sharpness) ?? UNSET_SHARPNESS;
  // The game's state belongs to the sharpness the running game uses: its own while it has an
  // active profile, else the general one.
  const runningProfile = running === null ? undefined : profileOf(setting.gameSharpness, running.appId);
  const usedGame = runningProfile?.active === true ? runningProfile.appId : null;
  const used = usedGame === (own ? game?.appId : null);
  const save = (next: Sharpness) => {
    if (game !== null && own) setGameSharpness(withSharpness(setting.gameSharpness, game.appId, next));
    else setSharpness(next);
  };
  return (
    <>
      {game === null ? (
        <NavRow
          title={t.service.profiles}
          count={setting.gameSharpness.length}
          subtitle={t.service.profilesSub}
          action={t.actions.open}
          onPress={() => {
            navigate("sharpnessProfiles");
          }}
        />
      ) : (
        <GameSharpnessRow setting={setting} game={game} own={own} />
      )}
      <SharpnessCard sharpness={shown} state={used ? state : null} onChange={save} />
    </>
  );
}

/**
 * The game's own sharpness, switched on and off like its own sound. Nothing is made until it is
 * switched on: the first time copies the general sharpness, and switched off, the profile is kept
 * for the next time.
 */
function GameSharpnessRow({ setting, game, own }: { setting: Settings; game: Game; own: boolean }) {
  const t = useMessages();
  const kept = profileOf(setting.gameSharpness, game.appId) !== undefined;
  return (
    <ToggleRow
      title={t.service.gameSharpness}
      subtitle={own ? t.power.gameProfileOn(game.name) : t.power.gameProfileOff(game.name)}
      {...(!own && kept ? { note: t.power.gameProfileKept } : {})}
      value={own}
      action={t.actions.toggle}
      onChange={(on) => {
        setGameSharpness(
          chooseOwnSharpness(setting.gameSharpness, game, setting.sharpness ?? UNSET_SHARPNESS, on),
        );
      }}
    />
  );
}

interface SharpnessCardProps {
  sharpness: Sharpness;
  /** The running game's state while this sharpness is the one it uses; null otherwise and until read. */
  state: SharpnessGameState | null;
  onChange: (sharpness: Sharpness) => void;
}

/** The switch in the head, and while it is on the strength: its scale and presets. */
function SharpnessCard({ sharpness, state, onChange }: SharpnessCardProps) {
  const t = useMessages();
  const { strength } = sharpness;
  const preset = sharpnessPresetOf(strength);
  const set = (next: number) => {
    onChange({ ...sharpness, strength: Math.min(MAX_SHARPNESS, Math.max(0, next)) });
  };
  return (
    <Card
      title={t.service.sharpness}
      subtitle={t.service.status[sharpnessStatus(sharpness, state)]}
      toggle={{
        value: sharpness.enabled,
        action: t.actions.toggle,
        onChange: (enabled) => {
          onChange({ ...sharpness, enabled });
        },
      }}
    >
      <span className="og-card__hint">{t.service.sharpnessNote}</span>
      <span className="og-card__hint">{t.service.launchNote}</span>
      <span className="og-card__label">{t.service.strength}</span>
      <span className="og-card__hint">{t.service.strengthNote}</span>
      <Slider
        label={t.service.strength}
        value={strength}
        min={0}
        max={MAX_SHARPNESS}
        step={SHARPNESS_STEP}
        track={filledTrack(strength, 0, MAX_SHARPNESS)}
        thumb="var(--og-accent)"
        notch={DEFAULT_SHARPNESS.strength}
        lessLabel={t.actions.less}
        moreLabel={t.actions.more}
        onChange={set}
      />
      <div className="og-slider__ends" aria-hidden="true">
        <span>0</span>
        <span>{MAX_SHARPNESS / 2}</span>
        <span>{MAX_SHARPNESS}</span>
      </div>
      <ChoiceGroup
        label={t.service.strength}
        choices={SHARPNESS_PRESETS.map((choice) => ({
          value: choice.id,
          label: t.service.presets[choice.id],
          detail: `${choice.value}%`,
        }))}
        value={preset?.id}
        action={t.actions.select}
        onChange={(id) => {
          set(SHARPNESS_PRESETS.find((choice) => choice.id === id)?.value ?? DEFAULT_SHARPNESS.strength);
        }}
        custom={{
          label: t.service.presets.custom,
          detail: preset === undefined ? `${strength}%` : "+",
          selected: preset === undefined,
        }}
      />
    </Card>
  );
}
