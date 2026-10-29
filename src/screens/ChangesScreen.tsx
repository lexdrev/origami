// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { Focusable } from "@decky/ui";
import { useEffect, useRef, useState } from "react";

import { useMessages } from "../i18n";
import { back } from "../navigation";
import { UISound } from "../sounds";
import { changes, info, refreshChanges, restoreAll } from "../state";
import { useStore } from "../store";
import { Alert, FactList, Header, List, Notice, Screen, SectionLabel } from "../ui/blocks";
import { Pressable } from "../ui/controls";
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

/**
 * "Restore everything", asked once more in place. The button itself turns into Cancel, so the
 * focus stays on it and the user steps right to confirm: Steam's focus cannot be moved into a
 * window drawn over the panel.
 */
function RestoreAll({ onRestored }: { onRestored: () => void }) {
  const t = useMessages();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const block = useRef<HTMLDivElement>(null);

  // The question opens above the focused button and pushes it past the panel's edge, while Steam
  // scrolls only when the focus moves: bring the whole question into view.
  useEffect(() => {
    if (asking) block.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [asking]);

  return (
    <div ref={block} className={asking ? "og-restore og-restore--asking" : "og-restore"}>
      {asking && (
        <>
          <span className="og-restore__title">{t.changes.restoreAsk}</span>
          <span className="og-restore__text">{t.changes.restoreText}</span>
          <span className="og-restore__note">{t.changes.restoreNote}</span>
        </>
      )}
      <Focusable className="og-actions" flow-children="row">
        <Pressable
          className={asking ? "og-button" : "og-button og-button--wide"}
          action={asking ? t.changes.cancel : t.changes.restore}
          disabled={busy}
          onPress={() => {
            setAsking(!asking);
          }}
        >
          {asking ? t.changes.cancel : t.changes.restore}
        </Pressable>
        {asking && (
          <Pressable
            className="og-button og-button--primary"
            action={t.changes.confirm}
            sound={UISound.Press}
            disabled={busy}
            onPress={() => {
              setBusy(true);
              void restoreAll().then((done) => {
                setBusy(false);
                setAsking(false);
                if (done) onRestored();
              });
            }}
          >
            {t.changes.confirm}
          </Pressable>
        )}
      </Focusable>
    </div>
  );
}
