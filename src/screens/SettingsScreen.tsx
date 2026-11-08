// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { Focusable, Navigation } from "@decky/ui";
import { useEffect } from "react";

import type { LanguageSetting } from "../backend";
import { useMessages, type Messages } from "../i18n";
import { back, navigate } from "../navigation";
import { unset } from "../problems";
import { changes, refreshChanges, settings, updateSettings } from "../state";
import { useStore } from "../store";
import { Card, Header, Screen, SectionLabel, SwitchLine } from "../ui/blocks";
import { UISound } from "../sounds";
import { ChoiceGroup, NavRow, Pressable, ToggleRow, type Choice } from "../ui/controls";
import { FoxMark, GearIcon } from "../ui/icons";
import { ownTabSummary, quickAccessColumn } from "../tabPosition";
import {
  checkForUpdates,
  currentVersion,
  forgetLastCheck,
  installUpdate,
  offeredRelease,
  RELEASES_PAGE,
  updateState,
  type UpdateState,
} from "../updates";
import { LoadFailed } from "./LoadFailed";

const REPOSITORY = "github.com/lexdrev/origami";
const LICENSE = "GPL-3.0";

/** Opens a page in Steam's browser, which shows over the closed side menus. */
function openPage(url: string) {
  Navigation.NavigateToExternalWeb(url);
  Navigation.CloseSideMenus();
}

export function SettingsScreen() {
  const t = useMessages();
  const current = useStore(settings);
  const journal = useStore(changes);
  const column = useStore(quickAccessColumn);

  useEffect(() => {
    void refreshChanges();
  }, []);

  const languages: Choice<LanguageSetting>[] = (["auto", "ru", "en"] as const).map((value) => ({
    value,
    label: t.settings.languages[value],
  }));

  return (
    <Screen onBack={back}>
      <Header onBack={back} icon={<GearIcon size={18} />} title={t.settings.title} />

      <SectionLabel>{t.settings.language}</SectionLabel>
      <ChoiceGroup
        label={t.settings.language}
        choices={languages}
        value={current.status === "ready" ? current.value.language : undefined}
        action={t.actions.select}
        onChange={(language) => void updateSettings({ language })}
      />

      <SectionLabel>{t.settings.system}</SectionLabel>
      <LoadFailed loads={[current]} />
      {current.status === "ready" && (
        <ToggleRow
          title={t.settings.manageTdp}
          subtitle={current.value.manageTdp ? t.settings.manageTdpOn : t.settings.manageTdpOff}
          note={current.value.manageTdp ? t.settings.manageTdpNote : t.settings.manageTdpOffNote}
          problem={unset(current.value.manageTdp)}
          value={current.value.manageTdp ?? false}
          action={t.actions.toggle}
          onChange={(manageTdp) => void updateSettings({ manageTdp })}
        />
      )}
      <NavRow
        title={t.settings.qamTab}
        subtitle={
          current.status === "ready"
            ? ownTabSummary(current.value.qamTab, current.value.qamTabBefore, column, t)
            : t.unknown
        }
        problem={current.status === "ready" && current.value.qamTab && column.arranger !== null}
        action={t.actions.open}
        onPress={() => {
          navigate("qamTab");
        }}
      />
      <NavRow
        title={t.settings.changes}
        subtitle={journal.status === "ready" ? t.settings.changesSummary(journal.value.length) : t.unknown}
        action={t.actions.open}
        onPress={() => {
          navigate("changes");
        }}
      />
      <UpdateCard />

      {/* The last stop of the D-pad: Steam scrolls only to the focus, so the block shows whole. */}
      <div className="og-about">
        <Pressable
          className="og-about__card"
          action={t.settings.openProject}
          sound={UISound.Press}
          onPress={() => {
            openPage(`https://${REPOSITORY}`);
          }}
        >
          <FoxMark size={26} />
          <span className="og-about__lines">
            <span className="og-about__name">
              <b>ORIGAMI</b> {currentVersion} · {LICENSE}
            </span>
            <span>{t.settings.slogan[0]}</span>
            <span>{t.settings.slogan[1]}</span>
            <span>{REPOSITORY}</span>
          </span>
        </Pressable>
      </div>
    </Screen>
  );
}

/** The card's line under its title: what the last check found. */
function updateSummary(state: UpdateState, texts: Messages["settings"]["updates"]): string {
  switch (state.status) {
    case "idle":
      return texts.idle(currentVersion);
    case "checking":
      return texts.checking(currentVersion);
    case "latest":
      return texts.latest(currentVersion);
    case "available":
      return texts.available(state.release.version);
    case "failed":
      return texts.failed;
    case "refused":
      return texts.refused;
  }
}

/**
 * Everything about updates in one card. The first button keeps its place while its words follow the
 * check, as Steam cannot move the focus to a new button: it checks, then updates. What's new opens
 * the releases on GitHub, the newest first; the daily check below is off until the user switches it on.
 */
function UpdateCard() {
  const t = useMessages();
  const texts = t.settings.updates;
  const state = useStore(updateState);
  const current = useStore(settings);
  const release = offeredRelease(state);
  const checking = state.status === "checking";
  let label = texts.check;
  if (release !== null) label = texts.update;
  else if (checking) label = texts.busy;

  return (
    <Card title={texts.title} subtitle={updateSummary(state, texts)} offer={state.status === "available"}>
      {/* Steam moves the focus only up and down by default; the two buttons go left and right too. */}
      <Focusable className="og-actions" flow-children="row">
        <Pressable
          className={release === null ? "og-button" : "og-button og-button--primary"}
          action={release === null ? t.actions.check : t.actions.update}
          sound={UISound.Press}
          disabled={checking}
          onPress={() => void (release === null ? checkForUpdates() : installUpdate(release))}
        >
          {label}
        </Pressable>
        <Pressable
          className="og-button"
          action={t.actions.open}
          sound={UISound.Press}
          onPress={() => {
            openPage(RELEASES_PAGE);
          }}
        >
          {texts.whatsNew}
        </Pressable>
      </Focusable>
      {state.status === "available" && <span className="og-card__subtitle">{texts.confirm}</span>}
      {state.status === "refused" && <span className="og-card__subtitle">{texts.download}</span>}
      {current.status === "ready" && (
        <>
          <span className="og-card__divider" aria-hidden="true" />
          <SwitchLine
            title={texts.daily}
            subtitle={current.value.updateCheck ? texts.dailyOn : texts.dailyOff}
            value={current.value.updateCheck}
            action={t.actions.toggle}
            onChange={(updateCheck) => {
              // Switched on again, it asks at once rather than a day after the last answer.
              if (!updateCheck) forgetLastCheck();
              void updateSettings({ updateCheck });
            }}
          />
        </>
      )}
    </Card>
  );
}
