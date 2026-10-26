// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { Focusable } from "@decky/ui";
import type { ReactNode } from "react";

import { ChevronIcon } from "./icons";

interface PressableProps {
  className: string;
  onPress: () => void;
  /** Shown by Steam next to the A button while the element has focus. */
  action: string;
  label?: string;
  pressed?: boolean;
  children: ReactNode;
}

/** Base of every interactive element: reachable with the D-pad, activated with A. */
export function Pressable({ className, onPress, action, label, pressed, children }: PressableProps) {
  return (
    <Focusable
      className={className}
      focusClassName="og-focused"
      noFocusRing
      role="button"
      aria-label={label}
      aria-pressed={pressed}
      onActivate={() => {
        onPress();
      }}
      onOKActionDescription={action}
    >
      {children}
    </Focusable>
  );
}

export function IconButton(props: Omit<PressableProps, "className">) {
  return <Pressable className="og-icon-button" {...props} />;
}

export interface Choice<T extends string> {
  value: T;
  label: string;
}

interface ChoiceGroupProps<T extends string> {
  label: string;
  choices: readonly Choice<T>[];
  value: T | undefined;
  action: string;
  onChange: (value: T) => void;
}

export function ChoiceGroup<T extends string>({ label, choices, value, action, onChange }: ChoiceGroupProps<T>) {
  return (
    <Focusable className="og-choices" role="group" aria-label={label}>
      {choices.map((choice) => {
        const selected = choice.value === value;
        return (
          <Pressable
            key={choice.value}
            className={selected ? "og-choice og-choice--selected" : "og-choice"}
            pressed={selected}
            action={action}
            onPress={() => {
              onChange(choice.value);
            }}
          >
            {choice.label}
          </Pressable>
        );
      })}
    </Focusable>
  );
}

interface NavRowProps {
  title: string;
  subtitle: string;
  action: string;
  onPress: () => void;
}

/** A row that opens another screen. */
export function NavRow({ title, subtitle, action, onPress }: NavRowProps) {
  return (
    <Pressable className="og-row" action={action} onPress={onPress}>
      <span className="og-row__title">{title}</span>
      <span className="og-row__sub">{subtitle}</span>
      <span className="og-row__chevron">
        <ChevronIcon />
      </span>
    </Pressable>
  );
}
