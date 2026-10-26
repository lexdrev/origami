// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

// Browser stand-in for Steam's Focusable: Tab moves focus, Enter or a click activates,
// Escape stands for the B button. Focus gets focusClassName, like on the console.

import type { FocusableProps, GamepadEvent } from "@decky/ui";
import { forwardRef, useState, type KeyboardEvent } from "react";

// ORIGAMI does not read the event details, so the stand sends none.
function gamepadEvent(): GamepadEvent {
  return new CustomEvent("vgp_onbuttondown");
}

export const Focusable = forwardRef<HTMLDivElement, FocusableProps>(function Focusable(props, ref) {
  const {
    children,
    className,
    focusClassName,
    onActivate,
    onCancelButton,
    noFocusRing,
    onOKActionDescription,
    onCancelActionDescription,
    focusWithinClassName,
    ...attributes
  } = props;
  const [focused, setFocused] = useState(false);
  const interactive = onActivate !== undefined;

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (interactive && event.target === event.currentTarget && event.key === "Enter") {
      onActivate(gamepadEvent());
    } else if (event.key === "Escape" && onCancelButton) {
      event.stopPropagation();
      onCancelButton(gamepadEvent());
    }
  };

  return (
    <div
      ref={ref}
      {...attributes}
      className={[className, focused && focusClassName].filter(Boolean).join(" ")}
      tabIndex={interactive ? 0 : undefined}
      onFocus={(event) => {
        if (event.target === event.currentTarget) setFocused(true);
      }}
      onBlur={() => {
        setFocused(false);
      }}
      onClick={
        interactive
          ? () => {
              onActivate(gamepadEvent());
            }
          : undefined
      }
      onKeyDown={onKeyDown}
    >
      {children}
    </div>
  );
});
