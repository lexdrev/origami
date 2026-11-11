// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { scrollingBox } from "./scrollbar";

// Steam scrolls the panel only as far as the element in focus needs, so coming back up to the first
// row under a header leaves the header, and the top of the panel, out of view. Before it scrolls to
// the element (scrollIntoView, block "nearest"), Steam asks each group above it marked
// scrollIntoViewWhenChildFocused. A screen gives an element that fits in the panel together with
// everything above it a scroll margin up to the panel's top, so Steam's scroll goes all the way up.
// The browser keeps to the margin only while the element itself is partly out of view; while it is
// all in view and the panel is not at its top, the screen scrolls the panel up itself.
// Steam also keeps the element its scroll padding (48 px) away from the panel's bottom, so that the
// next row shows: an element only fits clear of it, otherwise Steam scrolls as it always does.

/** The part of Steam's navigation node (CNavigationTreeNode) the screen reads. */
interface NavNode {
  Element: Element | undefined;
}

/** Steam's navigation properties for it, which @decky/ui does not type. */
interface ScrollHandler {
  scrollIntoViewWhenChildFocused: boolean;
  /**
   * Called with the element in focus, the one before it and the group itself. Returns true to leave
   * the group itself unscrolled; Steam then scrolls to the element.
   */
  fnScrollIntoViewHandler: (focused: NavNode, previous?: NavNode, group?: NavNode) => boolean;
}

export const scrollToTop: ScrollHandler = {
  scrollIntoViewWhenChildFocused: true,
  fnScrollIntoViewHandler: ({ Element: element }) => {
    // The panel lives in the quick access window, with its own HTMLElement.
    const view = element?.ownerDocument.defaultView;
    if (element && view && element instanceof view.HTMLElement) {
      const box = scrollingBox(element);
      if (box) {
        // "auto" is no padding.
        const padding = Number.parseFloat(view.getComputedStyle(box).scrollPaddingBottom) || 0;
        const margin = topMargin(element, box, padding);
        element.style.scrollMarginTop = margin;
        if (margin !== "" && box.scrollTop > 0) box.scrollTo({ top: 0, behavior: "smooth" });
      }
    }
    return true;
  },
};

/** Up to the box's top while the element fits above its bottom padding with all above it, else none. */
export function topMargin(element: HTMLElement, box: HTMLElement, paddingBottom: number): string {
  const rect = element.getBoundingClientRect();
  const top = rect.top - box.getBoundingClientRect().top + box.scrollTop;
  return top + rect.height <= box.clientHeight - paddingBottom ? `${Math.ceil(top)}px` : "";
}

// Rows of tiles longer than the panel: Steam scrolls only as far as the row in focus needs, so on a
// middle row the next one shows by its top edge alone. A group of rows keeps the row in focus in the
// middle of what shows of the panel, under the title row that stays over its top: the rows on both
// sides then show their names and values. The first row leaves the panel at its top and the last at
// its end, as that is as far as it scrolls. The group scrolls the panel itself, and gives the element
// scroll margins with which Steam's own scroll to it ends at the same place.

export const scrollToMiddle: ScrollHandler = {
  scrollIntoViewWhenChildFocused: true,
  fnScrollIntoViewHandler: ({ Element: element }) => {
    const view = element?.ownerDocument.defaultView;
    if (element && view && element instanceof view.HTMLElement) {
      const box = scrollingBox(element);
      if (box) {
        // Where the box's content starts in the window, however far it is scrolled.
        const start = box.getBoundingClientRect().top - box.scrollTop;
        const rect = element.getBoundingClientRect();
        const top = rect.top - start;
        const bottom = top + rect.height;
        const target = middleScroll(
          top,
          bottom,
          box.clientHeight,
          coveredTop(element, box, view),
          box.scrollHeight - box.clientHeight,
        );
        const style = view.getComputedStyle(box);
        const margins = scrollMargins(top, bottom, target, box.clientHeight, {
          // "auto" is no padding.
          top: Number.parseFloat(style.scrollPaddingTop) || 0,
          bottom: Number.parseFloat(style.scrollPaddingBottom) || 0,
        });
        element.style.scrollMarginTop = margins.top;
        element.style.scrollMarginBottom = margins.bottom;
        if (Math.abs(box.scrollTop - target) >= 1) box.scrollTo({ top: target, behavior: "smooth" });
      }
    }
    return true;
  },
};

/**
 * How much of the box's top a title row covers: the tab's title is a sticky element before the
 * screen, or before one of the elements the screen is in, and stays there as the box scrolls.
 */
function coveredTop(element: HTMLElement, box: HTMLElement, view: Window): number {
  const top = box.getBoundingClientRect().top;
  let covered = 0;
  for (let inner: Element | null = element; inner && inner !== box; inner = inner.parentElement) {
    for (let before = inner.previousElementSibling; before; before = before.previousElementSibling) {
      if (view.getComputedStyle(before).position === "sticky") {
        covered = Math.max(covered, before.getBoundingClientRect().bottom - top);
      }
    }
  }
  return covered;
}

/**
 * How far a box `height` px high, its top `covered` px under a title, stands for an element from
 * `top` to `bottom` px down its content: with the element in the middle of what shows, as far as
 * the box scrolls, which is `max` px.
 */
export function middleScroll(top: number, bottom: number, height: number, covered: number, max: number): number {
  const middle = covered + (height - covered) / 2;
  return Math.round(Math.min(Math.max((top + bottom) / 2 - middle, 0), Math.max(max, 0)));
}

/**
 * The scroll margins of an element from `top` to `bottom` px down the content with which a scroll to
 * it (scrollIntoView, block "nearest") leaves a box `height` px high scrolled by `target`: with them
 * the element fills the box between its scroll paddings exactly there. A margin below zero is one
 * the element reaches past.
 */
export function scrollMargins(
  top: number,
  bottom: number,
  target: number,
  height: number,
  padding: { top: number; bottom: number },
): { top: string; bottom: string } {
  return {
    top: `${Math.round(top - padding.top - target)}px`,
    bottom: `${Math.round(target + height - padding.bottom - bottom)}px`,
  };
}
