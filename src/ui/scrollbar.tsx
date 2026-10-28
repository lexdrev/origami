// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { useEffect, useRef, useState } from "react";

// Steam draws no scrollbar in the quick access panel, so a screen longer than the panel gives no
// sign of what is below. This bar sits at the right edge of the panel's scrolling box while there is
// more than fits: its thumb is as long as the part in view and stands where that part is. It only
// shows; Steam scrolls the panel after the focus.

/** Gap between the bar and the box's top, bottom and right edges. */
const INSET = 4;
const WIDTH = 3;
const MIN_THUMB = 24;

interface Bar {
  top: number;
  left: number;
  height: number;
  thumbTop: number;
  thumbHeight: number;
}

export function ScrollBar() {
  const anchor = useRef<HTMLSpanElement>(null);
  const [bar, setBar] = useState<Bar | null>(null);

  useEffect(() => {
    const element = anchor.current;
    // ORIGAMI's own screen: the root the anchor is in.
    const content = element?.parentElement;
    const scroller = element && scrollingBox(element);
    const view = element?.ownerDocument.defaultView;
    if (!element || !content || !scroller || !view) return undefined;

    const update = () => {
      setBar((previous) => {
        const next = measure(scroller, content);
        return sameBar(previous, next) ? previous : next;
      });
    };
    update();
    // The panel's elements live in the quick access window: its own observer sees them resize.
    const resizes = new view.ResizeObserver(update);
    resizes.observe(scroller);
    resizes.observe(content);
    scroller.addEventListener("scroll", update, { passive: true });
    // The panel slides in and out; its place settles when the slide ends.
    const document = element.ownerDocument;
    document.addEventListener("transitionend", update, true);
    document.addEventListener("animationend", update, true);
    document.addEventListener("focusin", update, true);
    return () => {
      resizes.disconnect();
      scroller.removeEventListener("scroll", update);
      document.removeEventListener("transitionend", update, true);
      document.removeEventListener("animationend", update, true);
      document.removeEventListener("focusin", update, true);
    };
  }, []);

  return (
    <>
      <span ref={anchor} className="og-scrollbar-anchor" aria-hidden="true" />
      {bar && (
        <span className="og-scrollbar" aria-hidden="true" style={{ top: bar.top, left: bar.left, height: bar.height }}>
          <span className="og-scrollbar__thumb" style={{ top: bar.thumbTop, height: bar.thumbHeight }} />
        </span>
      )}
    </>
  );
}

/** The nearest box above the element that scrolls its contents: the panel ORIGAMI is in. */
function scrollingBox(element: HTMLElement): HTMLElement | null {
  const view = element.ownerDocument.defaultView;
  for (let box = element.parentElement; box && view; box = box.parentElement) {
    const { overflowY } = view.getComputedStyle(box);
    if (overflowY === "auto" || overflowY === "scroll") return box;
  }
  return null;
}

/**
 * The bar for the box as it is scrolled now; null while all of the content is in view. It goes by the
 * content's end, not the box's: in Decky's tab the plugin's wrapper is as tall as the panel and sits
 * under Decky's title row and a 16 px gap, so the box scrolls some 40 px past the end of any plugin.
 */
export function measure(box: HTMLElement, content: HTMLElement): Bar | null {
  const { scrollTop, clientHeight } = box;
  const rect = box.getBoundingClientRect();
  const length = content.getBoundingClientRect().bottom - rect.top + scrollTop;
  if (length <= clientHeight + 1) return null;
  const track = rect.height - 2 * INSET;
  const thumbHeight = Math.max(MIN_THUMB, (track * clientHeight) / length);
  // A finger can still drag the box into Decky's empty space; the thumb stays at the bottom then.
  const thumbTop = ((track - thumbHeight) * Math.min(scrollTop, length - clientHeight)) / (length - clientHeight);
  return {
    top: rect.top + INSET,
    left: rect.right - INSET - WIDTH,
    height: track,
    thumbTop: Math.round(thumbTop),
    thumbHeight: Math.round(thumbHeight),
  };
}

function sameBar(a: Bar | null, b: Bar | null): boolean {
  if (a === null || b === null) return a === b;
  return (
    a.top === b.top &&
    a.left === b.left &&
    a.height === b.height &&
    a.thumbTop === b.thumbTop &&
    a.thumbHeight === b.thumbHeight
  );
}
