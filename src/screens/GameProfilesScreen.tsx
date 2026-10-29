// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { useEffect, useState } from "react";

import { summary, without } from "../gameProfiles";
import { openedProfile } from "../games";
import { useMessages } from "../i18n";
import { back, navigate } from "../navigation";
import { setGamePower, settings } from "../state";
import { useStore } from "../store";
import { Header, Screen } from "../ui/blocks";
import { NavRow } from "../ui/controls";
import { LoadFailed } from "./LoadFailed";

/** A second press of X within this time removes the profile; the first only asks for it. */
const REMOVE_WINDOW_MS = 3000;

/** The games with power settings of their own: A opens one, X twice removes it. */
export function GameProfilesScreen() {
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

  const header = <Header onBack={back} title={t.power.profiles} subtitle={t.power.profilesTitleSub} />;
  if (current.status !== "ready") {
    return (
      <Screen onBack={back}>
        {header}
        <LoadFailed loads={[current]} />
      </Screen>
    );
  }
  const { gamePower } = current.value;
  return (
    <Screen onBack={back}>
      {header}
      {gamePower.map((profile) => {
        const removing = asked === profile.appId;
        return (
          <NavRow
            key={profile.appId}
            title={profile.name}
            subtitle={removing ? t.power.removeAgain : summary(profile.power, t)}
            // Only a profile that waits says so; how the others differ shows inside them.
            note={removing ? summary(profile.power, t) : profile.active ? undefined : t.power.profileWaiting}
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
                setGamePower(without(gamePower, profile.appId));
              },
            }}
            onPress={() => {
              openedProfile.set({ appId: profile.appId, name: profile.name });
              navigate("gameProfile");
            }}
          />
        );
      })}
      <p className="og-note">{t.power.profilesHint}</p>
    </Screen>
  );
}

