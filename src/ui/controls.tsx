// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { Focusable } from "@decky/ui";
import type { ReactNode } from "react";

import { playSound, UISound } from "../sounds";
import { ChevronIcon } from "./icons";

interface PressableProps {
  className: string;
  onPress: () => void;
  /** Shown by Steam next to the A button while the element has focus. */
  action: string;
  label?: string;
  pressed?: boolean;
  /** Played on activation; screen changes play their own sound in navigation. */
  sound?: UISound;
  /** Stays focusable, so the D-pad path does not jump, but does nothing. */
  disabled?: boolean;
  children: ReactNode;
}

/** Base of every interactive element: reachable with the D-pad, activated with A or a tap. */
export function Pressable(props: PressableProps) {
  const { className, onPress, action, label, pressed, sound, disabled = false, children } = props;
  return (
    <Focusable
      className={disabled ? `${className} og-disabled` : className}
      focusClassName="og-focused"
      noFocusRing
      role="button"
      aria-label={label}
      aria-pressed={pressed}
      aria-disabled={disabled}
      onActivate={() => {
        if (disabled) return;
        if (sound !== undefined) playSound(sound);
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
            sound={UISound.Press}
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

interface ToggleRowProps {
  title: string;
  subtitle: string;
  value: boolean;
  action: string;
  onChange: (value: boolean) => void;
}

/** A row with the B2 switch; plays Steam's toggle sounds. */
export function ToggleRow({ title, subtitle, value, action, onChange }: ToggleRowProps) {
  return (
    <Pressable
      className="og-row og-toggle"
      action={action}
      pressed={value}
      sound={value ? UISound.ToggleOff : UISound.ToggleOn}
      onPress={() => {
        onChange(!value);
      }}
    >
      <span className="og-row__title">{title}</span>
      <span className="og-row__sub">{subtitle}</span>
      <span className={value ? "og-switch og-switch--on" : "og-switch"} aria-hidden="true">
        <span className="og-switch__knob" />
      </span>
    </Pressable>
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
