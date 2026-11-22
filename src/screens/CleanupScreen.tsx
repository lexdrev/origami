// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { useEffect, useState } from "react";

import { backend, type CleanupItem, type CleanupScan } from "../backend";
import {
  cloudOf,
  formatSize,
  installedCaches,
  itemNote,
  itemTitle,
  leftovers,
  mayLoseSaves,
  pickedSize,
  safeToRemove,
  type Cloud,
} from "../cleanup";
import { useMessages } from "../i18n";
import { back } from "../navigation";
import { UISound } from "../sounds";
import { cleanupScan, refreshCleanup } from "../state";
import { cloudSaves, steamName } from "../steamApps";
import { useStore } from "../store";
import { AskInPlace } from "../ui/ask";
import { Alert, Header, Notice, Screen } from "../ui/blocks";
import { CheckRow, FoldRow, Pressable } from "../ui/controls";
import { CheckIcon } from "../ui/icons";

interface Result {
  freed: number;
  /** The names of what stays. */
  failed: string[];
}

/** The Cleanup screen: the shader caches of the installed games, and what removed games left behind. */
export function CleanupScreen() {
  const t = useMessages();
  const scan = useStore(cleanupScan);

  // Games come and go between visits, so the folders are measured every time the screen opens.
  useEffect(() => {
    cleanupScan.set({ status: "loading" });
    void refreshCleanup();
  }, []);

  return (
    <Screen onBack={back}>
      <Header onBack={back} title={t.cleanup.title} subtitle={t.cleanup.subtitle} />
      {scan.status === "loading" && <p className="og-note">{t.cleanup.scanning}</p>}
      {scan.status === "failed" && <Alert title={t.errors.backend}>{scan.error}</Alert>}
      {scan.status === "ready" && <Found scan={scan.value} />}
    </Screen>
  );
}

function Found({ scan }: { scan: CleanupScan }) {
  const t = useMessages();
  const [clouds, setClouds] = useState<Record<number, Cloud | undefined>>({});
  const [picked, setPicked] = useState<ReadonlySet<string>>(new Set());
  const [result, setResult] = useState<Result | null>(null);
  // Both lists start folded: the screen opens on what there is, not on a long list of games.
  const [open, setOpen] = useState({ caches: false, leftovers: false });

  // Steam tells whether its cloud keeps the saves of a game whose prefix is left.
  useEffect(() => {
    let current = true;
    for (const item of scan.items) {
      const { appId } = item;
      if (item.kind !== "prefix" || item.owner !== "removed" || appId === null) continue;
      void cloudSaves(appId).then((cloud) => {
        if (current) setClouds((known) => ({ ...known, [appId]: cloud }));
      });
    }
    return () => {
      current = false;
    };
  }, [scan]);

  const storage = (
    <p className="og-note">
      {t.cleanup.storage(formatSize(scan.storage.free, t), formatSize(scan.storage.total, t))}
    </p>
  );
  if (scan.game) {
    return (
      <>
        {storage}
        <Alert title={t.cleanup.gameRuns} problem={false}>
          {t.cleanup.gameRunsText}
        </Alert>
      </>
    );
  }

  const left = leftovers(scan.items);
  const caches = installedCaches(scan.items);
  const safe = safeToRemove(scan.items, clouds);
  const chosen = scan.items.filter((item) => picked.has(item.key));
  const risky = chosen.filter((item) => mayLoseSaves(item, cloudOf(item, clouds))).length;
  const size = formatSize(pickedSize(scan.items, picked), t);
  const title = (item: CleanupItem) => itemTitle(item, item.appId === null ? null : steamName(item.appId), t);
  const toggle = (key: string, on: boolean) => {
    setPicked((before) => {
      const next = new Set(before);
      if (on) next.add(key);
      else next.delete(key);
      return next;
    });
  };
  // Under a folded list's name: what it holds in all, and what is picked inside.
  const summary = (items: readonly CleanupItem[], what: string) =>
    `${what} · ${formatSize(
      items.reduce((total, item) => total + item.size, 0),
      t,
    )}`;
  const pickedIn = (items: readonly CleanupItem[]) => {
    const count = items.filter((item) => picked.has(item.key)).length;
    return count === 0 ? undefined : t.cleanup.picked(count, formatSize(pickedSize(items, picked), t));
  };
  const row = (item: CleanupItem) => {
    const named = item.name !== null || (item.appId !== null && steamName(item.appId) !== null);
    const note = itemNote(item, cloudOf(item, clouds), named, t);
    return (
      <CheckRow
        key={item.key}
        title={title(item)}
        subtitle={`${t.cleanup.kinds[item.kind]} · ${formatSize(item.size, t)}`}
        note={note?.text}
        danger={note?.danger === true}
        value={picked.has(item.key)}
        action={t.actions.select}
        disabled={item.busy}
        onChange={(on) => {
          toggle(item.key, on);
        }}
      />
    );
  };

  return (
    <>
      {storage}
      {result !== null && (
        <>
          <Notice icon={<CheckIcon />}>{t.cleanup.freed(formatSize(result.freed, t))}</Notice>
          {result.failed.length > 0 && <Alert title={t.cleanup.failed}>{result.failed.join(" · ")}</Alert>}
        </>
      )}

      <FoldRow
        title={t.cleanup.caches}
        count={caches.length}
        subtitle={caches.length === 0 ? t.cleanup.noCaches : summary(caches, t.cleanup.cachesSub)}
        note={pickedIn(caches)}
        open={open.caches}
        action={t.actions.open}
        disabled={caches.length === 0}
        onToggle={() => {
          setOpen({ ...open, caches: !open.caches });
        }}
      />
      {open.caches && caches.length > 0 && (
        <>
          <p className="og-note">{t.cleanup.cachesHint}</p>
          {caches.map(row)}
        </>
      )}

      {scan.complete ? (
        <FoldRow
          title={t.cleanup.leftovers}
          count={left.length}
          subtitle={left.length === 0 ? t.cleanup.noLeftovers : summary(left, t.cleanup.leftoversSub)}
          note={pickedIn(left)}
          open={open.leftovers}
          action={t.actions.open}
          disabled={left.length === 0}
          onToggle={() => {
            setOpen({ ...open, leftovers: !open.leftovers });
          }}
        />
      ) : (
        <Alert title={t.cleanup.incomplete} problem={false}>
          {t.cleanup.incompleteText}
        </Alert>
      )}
      {open.leftovers && left.length > 0 && (
        <>
          <p className="og-note">{t.cleanup.leftoversHint}</p>
          {left.map(row)}
          <Pressable
            className="og-button"
            action={t.actions.select}
            sound={UISound.Press}
            disabled={safe.length === 0 || safe.every((key) => picked.has(key))}
            onPress={() => {
              setPicked((before) => new Set([...before, ...safe]));
            }}
          >
            {t.cleanup.pickSafe}
          </Pressable>
        </>
      )}

      {scan.items.length > 0 && (
        <AskInPlace
          action={chosen.length === 0 ? t.cleanup.pickFirst : t.cleanup.remove(size)}
          title={t.cleanup.ask}
          text={t.cleanup.askText(chosen.length, size)}
          danger={risky > 0 ? t.cleanup.askSaves(risky) : undefined}
          cancel={t.changes.cancel}
          confirm={t.cleanup.confirm}
          disabled={chosen.length === 0}
          onConfirm={async () => {
            const names = new Map(chosen.map((item) => [item.key, title(item)]));
            try {
              const cleaned = await backend.cleanUp(chosen.map((item) => item.key));
              setResult({ freed: cleaned.freed, failed: cleaned.failed.map((key) => names.get(key) ?? key) });
            } catch (error) {
              // The backend did not answer: the new scan shows what is still there.
              console.warn("ORIGAMI: the cleanup did not finish", error);
              setResult({ freed: 0, failed: [...names.values()] });
            }
            await refreshCleanup();
          }}
        />
      )}
    </>
  );
}
