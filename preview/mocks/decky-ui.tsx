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
    // The stand has no D-pad; Tab and the keyboard stand in for it.
    onGamepadDirection: _onGamepadDirection,
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

// The D-pad buttons ORIGAMI reads, with Steam's numbers; Tab stands in for them on the stand.
export const GamepadButton = { DIR_LEFT: 11, DIR_RIGHT: 12 } as const;

// Steam's window store and navigation; the stand has no quick access menu or routes.
export const Router = {};
export const Navigation = {
  Navigate: () => undefined,
  NavigateToExternalWeb: () => undefined,
  CloseSideMenus: () => undefined,
};

// Steam's webpack modules; the stand has none, so Steam's stores read as missing.
export const findModuleByExport = () => undefined;
