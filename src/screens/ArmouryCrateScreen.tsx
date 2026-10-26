// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import type { ButtonAction } from "../backend";
import { useMessages } from "../i18n";
import { back } from "../navigation";
import { settings, updateSettings } from "../state";
import { useStore } from "../store";
import { Header, Screen, SectionLabel } from "../ui/blocks";
import { OptionList } from "../ui/controls";
import { HOLD_ACTIONS, holdText, PRESS_ACTIONS, pressText } from "./armouryCrate";

export function ArmouryCrateScreen() {
  const t = useMessages();
  const current = useStore(settings);
  const options = (actions: readonly ButtonAction[], text: typeof pressText) =>
    actions.map((action) => ({ value: action, ...text(action, t) }));

  return (
    <Screen onBack={back}>
      <Header onBack={back} title={t.armouryCrate.title} subtitle={t.armouryCrate.subtitle} />
      {current.status === "ready" && (
        <>
          <SectionLabel>{t.armouryCrate.press}</SectionLabel>
          <OptionList
            label={t.armouryCrate.press}
            options={options(PRESS_ACTIONS, pressText)}
            value={current.value.armouryCrate}
            action={t.actions.select}
            onChange={(armouryCrate) => void updateSettings({ armouryCrate })}
          />
          <SectionLabel>{t.armouryCrate.hold}</SectionLabel>
          {/* Above the choices: below the last one Steam's scrolling, which follows focus, never gets there. */}
          <span className="og-hint">{t.armouryCrate.holdHint}</span>
          <OptionList
            label={t.armouryCrate.hold}
            options={options(HOLD_ACTIONS, holdText)}
            value={current.value.armouryCrateHold}
            action={t.actions.select}
            onChange={(armouryCrateHold) => void updateSettings({ armouryCrateHold })}
          />
        </>
      )}
    </Screen>
  );
}
