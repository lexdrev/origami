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
interface ScrollToTop {
  scrollIntoViewWhenChildFocused: boolean;
  /** Returns true to leave the group itself unscrolled; Steam then scrolls to the element. */
  fnScrollIntoViewHandler: (focused: NavNode) => boolean;
}

export const scrollToTop: ScrollToTop = {
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
