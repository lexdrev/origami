// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { useEffect, useState } from "react";

import { useMessages } from "../i18n";
import { back } from "../navigation";
import { changes, info, refreshChanges, restoreAll } from "../state";
import { useStore } from "../store";
import { Alert, FactList, Header, List, Notice, Screen, SectionLabel } from "../ui/blocks";
import { AskInPlace } from "../ui/ask";
import { CheckIcon } from "../ui/icons";
import { systemFacts } from "./system";

export function ChangesScreen() {
  const t = useMessages();
  const plugin = useStore(info);
  const journal = useStore(changes);
  const [restored, setRestored] = useState(false);

  useEffect(() => {
    void refreshChanges();
  }, []);

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
            <Notice icon={<CheckIcon />}>{restored ? t.changes.restored : t.changes.nothingChanged}</Notice>
          ) : (
            <>
              <List
                items={journal.value.map(
                  ({ module, key }) => t.changes.labels[`${module}.${key}`] ?? `${module} · ${key}`,
                )}
              />
              <RestoreAll
                onRestored={() => {
                  setRestored(true);
                }}
              />
            </>
          )}
        </>
      )}
      {journal.status === "failed" && <Alert title={t.errors.backend}>{journal.error}</Alert>}
    </Screen>
  );
}

/** "Restore everything", asked once more in place of its button. */
function RestoreAll({ onRestored }: { onRestored: () => void }) {
  const t = useMessages();
  return (
    <AskInPlace
      action={t.changes.restore}
      title={t.changes.restoreAsk}
      text={t.changes.restoreText}
      note={t.changes.restoreNote}
      cancel={t.changes.cancel}
      confirm={t.changes.confirm}
      onConfirm={async () => {
        if (await restoreAll()) onRestored();
      }}
    />
  );
}
