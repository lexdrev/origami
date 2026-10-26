// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import type { LanguageSetting } from "../backend";
import { useMessages } from "../i18n";
import { back, navigate } from "../navigation";
import { changes, info, settings, updateSettings } from "../state";
import { useStore } from "../store";
import { Header, Screen, SectionLabel } from "../ui/blocks";
import { ChoiceGroup, NavRow, type Choice } from "../ui/controls";
import { FoxMark, GearIcon } from "../ui/icons";

const REPOSITORY = "github.com/lexdrev/origami";
const LICENSE = "GPL-3.0";

export function SettingsScreen() {
  const t = useMessages();
  const current = useStore(settings);
  const journal = useStore(changes);
  const plugin = useStore(info);

  const languages: Choice<LanguageSetting>[] = (["auto", "ru", "en"] as const).map((value) => ({
    value,
    label: t.settings.languages[value],
  }));

  return (
    <Screen onBack={back}>
      <Header onBack={back} icon={<GearIcon size={22} />} title={t.settings.title} />

      <SectionLabel>{t.settings.language}</SectionLabel>
      <ChoiceGroup
        label={t.settings.language}
        choices={languages}
        value={current.status === "ready" ? current.value.language : undefined}
        action={t.actions.select}
        onChange={(language) => void updateSettings({ language })}
      />

      <SectionLabel>{t.settings.system}</SectionLabel>
      <NavRow
        title={t.settings.changes}
        subtitle={journal.status === "ready" ? t.settings.changesSummary(journal.value.length) : t.unknown}
        action={t.actions.open}
        onPress={() => {
          navigate("changes");
        }}
      />

      <div className="og-about">
        <FoxMark size={30} />
        <span className="og-about__lines">
          <span className="og-about__name">
            <b>ORIGAMI</b> {plugin.status === "ready" ? plugin.value.version : ""} · {LICENSE}
          </span>
          <span>{t.settings.slogan[0]}</span>
          <span>{t.settings.slogan[1]}</span>
          <span>{REPOSITORY}</span>
        </span>
      </div>
    </Screen>
  );
}
