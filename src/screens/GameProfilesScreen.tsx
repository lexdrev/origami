// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { useEffect, useState } from "react";

import type { Settings } from "../backend";
import { soundSummary, summary, without } from "../gameProfiles";
import { openedProfile } from "../games";
import { useMessages, type Messages } from "../i18n";
import { back, navigate, type ScreenId } from "../navigation";
import { setGamePower, setGameSound, settings } from "../state";
import { useStore } from "../store";
import { Header, Screen } from "../ui/blocks";
import { NavRow } from "../ui/controls";
import { LoadFailed } from "./LoadFailed";

/** A second press of X within this time removes the profile; the first only asks for it. */
const REMOVE_WINDOW_MS = 3000;

/** The games with power settings of their own. */
export function GameProfilesScreen() {
  const t = useMessages();
  return (
    <GameList
      subtitle={t.power.profilesTitleSub}
      hint={t.power.profilesHint}
      opens="gameProfile"
      select={(setting) => setting.gamePower}
      describe={(profile, messages) => summary(profile.power, messages)}
      keep={setGamePower}
    />
  );
}

/** The games with a sound of their own. */
export function GameSoundsScreen() {
  const t = useMessages();
  return (
    <GameList
      subtitle={t.sound.profilesTitleSub}
      hint={t.sound.profilesHint}
      opens="gameSound"
      select={(setting) => setting.gameSound}
      describe={(profile, messages) => soundSummary(profile.sound, messages)}
      keep={setGameSound}
    />
  );
}

interface Listed {
  appId: number;
  name: string;
  active: boolean;
}

interface GameListProps<T extends Listed> {
  /** Under the title: whose profiles these are. */
  subtitle: string;
  /** Under the list: how a game gets here. */
  hint: string;
  /** The screen a profile opens in. */
  opens: ScreenId;
  select: (setting: Settings) => readonly T[];
  /** What a profile sets, in a line. */
  describe: (profile: T, t: Messages) => string;
  /** Saves the list without the removed profile. */
  keep: (profiles: T[]) => void;
}

/** A list of games' profiles: A opens one, X twice removes it. */
function GameList<T extends Listed>({ subtitle, hint, opens, select, describe, keep }: GameListProps<T>) {
  const t = useMessages();
  const current = useStore(settings);
  const [asked, setAsked] = useState<number | null>(null);

  useEffect(() => {
    if (asked === null) return undefined;
    const timer = setTimeout(() => {
      setAsked(null);
    }, REMOVE_WINDOW_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [asked]);

  const header = <Header onBack={back} title={t.power.profiles} subtitle={subtitle} />;
  if (current.status !== "ready") {
    return (
      <Screen onBack={back}>
        {header}
        <LoadFailed loads={[current]} />
      </Screen>
    );
  }
  const profiles = select(current.value);
  return (
    <Screen onBack={back}>
      {header}
      {profiles.map((profile) => {
        const removing = asked === profile.appId;
        const line = describe(profile, t);
        return (
          <NavRow
            key={profile.appId}
            title={profile.name}
            subtitle={removing ? t.power.removeAgain : line}
            // Only a profile that waits says so; how the others differ shows inside them.
            note={removing ? line : profile.active ? undefined : t.power.profileWaiting}
            problem={removing}
            action={t.actions.open}
            secondary={{
              action: t.power.removeProfile,
              onPress: () => {
                if (!removing) {
                  setAsked(profile.appId);
                  return;
                }
                setAsked(null);
                keep(without(profiles, profile.appId));
              },
            }}
            onPress={() => {
              openedProfile.set({ appId: profile.appId, name: profile.name });
              navigate(opens);
            }}
          />
        );
      })}
      <p className="og-note">{hint}</p>
    </Screen>
  );
}
