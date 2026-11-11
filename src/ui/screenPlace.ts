// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { useEffect, useLayoutEffect, useRef, type RefObject } from "react";

import { useScreenDepth } from "../navigation";
import { scrollingBox } from "./scrollbar";

// Steam scrolls the panel only when the focus moves, and a screen that shows has no focus until
// the stick moves. So a screen that opened stayed scrolled as the one before left it, and coming
// back, the first move of the stick went to the screen's first element, not to the one the user
// had left. As the screens change, a screen that opens starts at its top, and one come back to
// stands as it was left, with the focus on the element that opened the other.

/** Steam's class on every element its navigation knows. */
const FOCUSABLE = ".Focusable";

/** The element in focus as a screen was left: its place among the screen's focusable elements. */
export interface Opener {
  index: number;
  /** How many focusable elements the screen had; another count is another layout. */
  count: number;
}

/** The place of that element in a screen that has `count` focusable elements now; null if none. */
export function openerAt(count: number, opener: Opener | undefined): number | null {
  if (opener?.count !== count || opener.index >= count) return null;
  return opener.index;
}

interface Left extends Opener {
  top: number;
}

/** Keeps the panel that holds `anchor`, and the focus, where the screen on top belongs. */
export function useScreenPlace(anchor: RefObject<HTMLElement | null>): void {
  const depth = useScreenDepth();
  const state = useRef<{ depth: number; top: number; focused: Opener | null; left: (Left | undefined)[] }>({
    depth,
    top: 0,
    focused: null,
    left: [],
  });

  // Where the screen on top is scrolled and what has the focus, as they change.
  useEffect(() => {
    const root = anchor.current;
    const box = root && scrollingBox(root);
    if (!root || !box) return undefined;
    const scrolled = () => {
      state.current.top = box.scrollTop;
    };
    const focused = (event: FocusEvent) => {
      // The panel's elements live in the quick access window: its Element is not this one's.
      const target = event.target as Element | null;
      const element = target?.closest(FOCUSABLE);
      if (!element) return;
      const all = Array.from(root.querySelectorAll(FOCUSABLE));
      state.current.focused = { index: all.indexOf(element), count: all.length };
    };
    box.addEventListener("scroll", scrolled, { passive: true });
    root.addEventListener("focusin", focused);
    return () => {
      box.removeEventListener("scroll", scrolled);
      root.removeEventListener("focusin", focused);
    };
  }, [anchor]);

  // Before the browser paints the new screen.
  useLayoutEffect(() => {
    const { current } = state;
    if (depth === current.depth) return;
    const root = anchor.current;
    const box = root && scrollingBox(root);
    let top = 0;
    let opener: HTMLElement | null = null;
    if (depth > current.depth) {
      const { focused } = current;
      current.left[current.depth - 1] = focused === null ? undefined : { ...focused, top: current.top };
    } else if (root) {
      const left = current.left[depth - 1];
      const all = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE));
      const index = openerAt(all.length, left);
      if (left !== undefined && index !== null) {
        top = left.top;
        opener = all[index] ?? null;
      }
      current.left.length = depth - 1;
    }
    current.depth = depth;
    current.top = top;
    current.focused = null;
    box?.scrollTo({ top, behavior: "instant" });
    // Steam's navigation follows the element's own focus, and scrolls to it by its rules.
    opener?.focus({ preventScroll: true });
  }, [anchor, depth]);
}
