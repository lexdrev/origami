// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { Focusable } from "@decky/ui";
import { useEffect, useRef, useState } from "react";

import { UISound } from "../sounds";
import { Pressable } from "./controls";

interface AskInPlaceProps {
  /** The button's own name, before it is pressed. */
  action: string;
  /** The question and what the answer does, shown once the button is pressed. */
  title: string;
  text: string;
  /** A grey line under the text. */
  note?: string | undefined;
  /** A red line under the text: what is lost for good. */
  danger?: string | undefined;
  cancel: string;
  confirm: string;
  /** The button is there but does nothing, such as with nothing picked. */
  disabled?: boolean;
  onConfirm: () => Promise<void>;
}

/**
 * A button that asks once more in place. The button itself turns into Cancel, so the focus stays
 * on it and the user steps right to confirm: Steam's focus cannot be moved into a window drawn
 * over the panel.
 */
export function AskInPlace(props: AskInPlaceProps) {
  const { action, title, text, note, danger, cancel, confirm, disabled = false, onConfirm } = props;
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
          <span className="og-restore__title">{title}</span>
          <span className="og-restore__text">{text}</span>
          {danger !== undefined && <span className="og-restore__danger">{danger}</span>}
          {note !== undefined && <span className="og-restore__note">{note}</span>}
        </>
      )}
      <Focusable className="og-actions" flow-children="row">
        <Pressable
          className={asking ? "og-button" : "og-button og-button--wide"}
          action={asking ? cancel : action}
          sound={UISound.Press}
          disabled={busy || (disabled && !asking)}
          onPress={() => {
            setAsking(!asking);
          }}
        >
          {asking ? cancel : action}
        </Pressable>
        {asking && (
          <Pressable
            className="og-button og-button--primary"
            action={confirm}
            sound={UISound.Press}
            disabled={busy}
            onPress={() => {
              setBusy(true);
              void onConfirm().finally(() => {
                setBusy(false);
                setAsking(false);
              });
            }}
          >
            {confirm}
          </Pressable>
        )}
      </Focusable>
    </div>
  );
}
