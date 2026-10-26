// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { useMessages } from "../i18n";
import { back } from "../navigation";
import { changes, info } from "../state";
import { useStore } from "../store";
import { Alert, FactList, Header, List, Notice, Screen, SectionLabel } from "../ui/blocks";
import { CheckIcon } from "../ui/icons";
import { systemFacts } from "./system";

export function ChangesScreen() {
  const t = useMessages();
  const plugin = useStore(info);
  const journal = useStore(changes);

  return (
    <Screen onBack={back}>
      <Header onBack={back} title={t.changes.title} subtitle={t.changes.subtitle} />

      <SectionLabel>{t.changes.system}</SectionLabel>
      {plugin.status === "ready" && <FactList facts={systemFacts(plugin.value, t)} />}
      {plugin.status === "failed" && <Alert title={t.errors.backend}>{plugin.error}</Alert>}

      {journal.status === "ready" && (
        <>
          <SectionLabel>{t.changes.changed(journal.value.length)}</SectionLabel>
          {journal.value.length === 0 ? (
            <Notice icon={<CheckIcon />}>{t.changes.nothingChanged}</Notice>
          ) : (
            <List
              items={journal.value.map(
                ({ module, key }) => t.changes.labels[`${module}.${key}`] ?? `${module} · ${key}`,
              )}
            />
          )}
        </>
      )}
      {journal.status === "failed" && <Alert title={t.errors.backend}>{journal.error}</Alert>}
    </Screen>
  );
}
