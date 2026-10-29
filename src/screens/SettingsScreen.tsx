// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { Navigation } from "@decky/ui";
import { useEffect } from "react";

import type { LanguageSetting } from "../backend";
import { useMessages } from "../i18n";
import { back, navigate } from "../navigation";
import { unset } from "../problems";
import { changes, info, refreshChanges, settings, updateSettings } from "../state";
import { useStore } from "../store";
import { Header, Screen, SectionLabel } from "../ui/blocks";
import { UISound } from "../sounds";
import { ChoiceGroup, NavRow, Pressable, ToggleRow, type Choice } from "../ui/controls";
import { FoxMark, GearIcon } from "../ui/icons";
import { ownTabSummary, quickAccessColumn } from "../tabPosition";

const REPOSITORY = "github.com/lexdrev/origami";
const LICENSE = "GPL-3.0";

export function SettingsScreen() {
  const t = useMessages();
  const current = useStore(settings);
  const journal = useStore(changes);
  const plugin = useStore(info);
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

      {/* The last stop of the D-pad: Steam scrolls only to the focus, so the block shows whole. */}
      <div className="og-about">
        <Pressable
          className="og-about__card"
          action={t.settings.openProject}
          sound={UISound.Press}
          onPress={() => {
            Navigation.NavigateToExternalWeb(`https://${REPOSITORY}`);
            Navigation.CloseSideMenus();
          }}
        >
          <FoxMark size={26} />
          <span className="og-about__lines">
            <span className="og-about__name">
              <b>ORIGAMI</b> {plugin.status === "ready" ? plugin.value.version : ""} · {LICENSE}
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
