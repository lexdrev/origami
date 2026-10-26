// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { useMessages } from "../i18n";
import { back } from "../navigation";
import { rescuedPresses } from "../qamAssist";
import { settings, updateSettings } from "../state";
import { useStore } from "../store";
import { Header, Screen } from "../ui/blocks";
import { ToggleRow } from "../ui/controls";

export function GamepadScreen() {
  const t = useMessages();
  const current = useStore(settings);
  const rescued = useStore(rescuedPresses);

  return (
    <Screen onBack={back}>
      <Header onBack={back} title={t.gamepad.title} />
      {current.status === "ready" && (
        <ToggleRow
          title={t.gamepad.qamAssist}
          subtitle={current.value.qamAssist ? t.gamepad.qamAssistOn(rescued) : t.gamepad.qamAssistOff}
          problem={!current.value.qamAssist}
          value={current.value.qamAssist}
          action={t.actions.toggle}
          onChange={(qamAssist) => void updateSettings({ qamAssist })}
        />
      )}
    </Screen>
  );
}
