// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import type { LanguageSetting } from "../backend";
import { LANGUAGE_NAMES, LANGUAGES, useMessages } from "../i18n";
import { back } from "../navigation";
import { settings, steamLanguage, updateSettings } from "../state";
import { useStore } from "../store";
import { Header, Screen } from "../ui/blocks";
import { OptionList, type Option } from "../ui/controls";
import { LoadFailed } from "./LoadFailed";

/** The language of ORIGAMI: Steam's own, or one of those ORIGAMI has, each under its own name. */
export function LanguageScreen() {
  const t = useMessages();
  const current = useStore(settings);
  const steam = useStore(steamLanguage);
  const options: Option<LanguageSetting>[] = [
    { value: "auto", name: t.settings.likeSteam, detail: t.settings.likeSteamNow(LANGUAGE_NAMES[steam]) },
    ...LANGUAGES.map((language) => ({ value: language, name: LANGUAGE_NAMES[language] })),
  ];

  return (
    <Screen onBack={back}>
      <Header onBack={back} title={t.settings.language} subtitle={t.settings.languageSubtitle} />
      <LoadFailed loads={[current]} />
      {current.status === "ready" && (
        <OptionList
          label={t.settings.language}
          options={options}
          value={current.value.language}
          action={t.actions.select}
          onChange={(language) => void updateSettings({ language })}
        />
      )}
    </Screen>
  );
}
