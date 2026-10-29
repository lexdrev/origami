// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { Focusable } from "@decky/ui";

import { useMessages } from "../i18n";
import { back } from "../navigation";
import { UISound } from "../sounds";
import { settings, updateSettings } from "../state";
import { useStore } from "../store";
import {
  FIRST_TAB,
  ownTabIndex,
  positionAt,
  quickAccessColumn,
  tabName,
  type ColumnTab,
  type TabPosition,
} from "../tabPosition";
import { Alert, Header, Screen, SectionLabel } from "../ui/blocks";
import { IconButton, Pressable, ToggleRow } from "../ui/controls";
import { DownIcon, UpIcon } from "../ui/icons";

/** Whether ORIGAMI has its own quick access tab, and where it stands in the column. */
export function QamTabScreen() {
  const t = useMessages();
  const current = useStore(settings);
  const column = useStore(quickAccessColumn);
  const place = (position: TabPosition) => void updateSettings({ qamTabBefore: position });

  return (
    <Screen onBack={back}>
      <Header onBack={back} title={t.qamTab.title} subtitle={t.qamTab.subtitle} />
      {current.status === "ready" && (
        <>
          <ToggleRow
            title={t.qamTab.own}
            subtitle={current.value.qamTab ? t.qamTab.ownOn : t.qamTab.ownOff}
            value={current.value.qamTab}
            action={t.actions.toggle}
            onChange={(qamTab) => void updateSettings({ qamTab })}
          />
          {current.value.qamTab && column.arranger !== null && (
            <>
              <SectionLabel>{t.qamTab.place}</SectionLabel>
              <Alert title={t.qamTab.arranged(column.arranger.name)}>{t.qamTab.arrangedText}</Alert>
            </>
          )}
          {current.value.qamTab && column.arranger === null && (
            <>
              <SectionLabel>{t.qamTab.place}</SectionLabel>
              <span className="og-hint">{t.qamTab.placeHint}</span>
              <Column
                column={column.tabs}
                index={ownTabIndex(column.tabs, current.value.qamTabBefore)}
                onMove={(index) => {
                  place(positionAt(column.tabs, index));
                }}
              />
              <Focusable className="og-actions" flow-children="row">
                <Pressable
                  className="og-button"
                  action={t.actions.select}
                  sound={UISound.Press}
                  onPress={() => {
                    place(FIRST_TAB);
                  }}
                >
                  {t.qamTab.toTop}
                </Pressable>
                <Pressable
                  className="og-button"
                  action={t.actions.select}
                  sound={UISound.Press}
                  onPress={() => {
                    place(null);
                  }}
                >
                  {t.qamTab.toBottom}
                </Pressable>
              </Focusable>
            </>
          )}
        </>
      )}
    </Screen>
  );
}

interface ColumnProps {
  column: readonly ColumnTab[];
  /** ORIGAMI's index among the other tabs. */
  index: number;
  onMove: (index: number) => void;
}

/** The quick access column top to bottom, with ORIGAMI's row and its up and down buttons. */
function Column({ column, index, onMove }: ColumnProps) {
  const t = useMessages();
  const row = (tab: ColumnTab, number: number) => (
    <div key={tab.key} className="og-column__item">
      <span className="og-column__number">{number}</span>
      <span className="og-column__name">{tabName(tab, t)}</span>
    </div>
  );

  return (
    <div className="og-column">
      {column.slice(0, index).map((tab, i) => row(tab, i + 1))}
      <Focusable className="og-column__item og-column__item--own" flow-children="row">
        <span className="og-column__number">{index + 1}</span>
        <span className="og-column__name">ORIGAMI</span>
        <IconButton
          label={t.qamTab.up}
          action={t.qamTab.up}
          sound={UISound.Press}
          disabled={index === 0}
          onPress={() => {
            onMove(index - 1);
          }}
        >
          <UpIcon />
        </IconButton>
        <IconButton
          label={t.qamTab.down}
          action={t.qamTab.down}
          sound={UISound.Press}
          disabled={index === column.length}
          onPress={() => {
            onMove(index + 1);
          }}
        >
          <DownIcon />
        </IconButton>
      </Focusable>
      {column.slice(index).map((tab, i) => row(tab, index + i + 2))}
    </div>
  );
}
