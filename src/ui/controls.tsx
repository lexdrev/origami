// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { Focusable, GamepadButton, type GamepadEvent } from "@decky/ui";
import type { CSSProperties, MouseEvent, ReactNode } from "react";

import { playSound, UISound } from "../sounds";
import { ChevronIcon, WarningIcon } from "./icons";

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
  style?: CSSProperties;
  children?: ReactNode;
}

/** Base of every interactive element: reachable with the D-pad, activated with A or a tap. */
export function Pressable(props: PressableProps) {
  const { className, onPress, action, label, pressed, sound, disabled = false, style, children } = props;
  return (
    <Focusable
      className={disabled ? `${className} og-disabled` : className}
      style={style}
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

// Four and more choices share a narrow row: a smaller font keeps long words off the edges.
const DENSE_CHOICES = 4;

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
    <Focusable
      className={choices.length >= DENSE_CHOICES ? "og-choices og-choices--dense" : "og-choices"}
      flow-children="row"
      role="group"
      aria-label={label}
    >
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
  /** The subtitle names a problem the switch fixes (style B2: red frame, triangle and text). */
  problem?: boolean;
  onChange: (value: boolean) => void;
}

/** A row with the B2 switch; plays Steam's toggle sounds. */
export function ToggleRow({ title, subtitle, value, action, problem = false, onChange }: ToggleRowProps) {
  return (
    <Pressable
      className={problem ? "og-row og-toggle og-row--problem" : "og-row og-toggle"}
      action={action}
      pressed={value}
      sound={value ? UISound.ToggleOff : UISound.ToggleOn}
      onPress={() => {
        onChange(!value);
      }}
    >
      <span className="og-row__title">{title}</span>
      <span className="og-row__sub">
        {problem && <WarningIcon size={12} />}
        {subtitle}
      </span>
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

interface SliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  /** The value runs in a circle, like the hue: past the end it starts again. */
  wrap?: boolean;
  /** CSS background of the track. */
  track: string;
  /** CSS colour of the thumb. */
  thumb: string;
  lessLabel: string;
  moreLabel: string;
  onChange: (value: number) => void;
}

/**
 * A B2 slider. With the D-pad the track is the whole control: focus lands on it from above or
 * below and left and right move it (holding repeats). The − and + buttons and a tap on the track
 * are for the touch screen, so the buttons stay out of the D-pad path.
 */
export function Slider(props: SliderProps) {
  const { label, value, min, max, step, wrap = false, track, thumb, lessLabel, moreLabel, onChange } = props;
  const span = max - min;
  const set = (next: number) => {
    onChange(wrap ? min + ((((next - min) % (span + 1)) + span + 1) % (span + 1)) : Math.min(max, Math.max(min, next)));
  };
  // Steam takes any result but false as "handled" and then moves no focus at all, so up and
  // down must answer false to leave the slider.
  const onDirection = (event: GamepadEvent): boolean => {
    const { button } = event.detail;
    if (button !== GamepadButton.DIR_LEFT && button !== GamepadButton.DIR_RIGHT) return false;
    set(value + (button === GamepadButton.DIR_LEFT ? -1 : 1) * step);
    return true;
  };
  const onTap = (event: MouseEvent<HTMLDivElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    set(Math.round(min + ((event.clientX - box.left) / box.width) * span));
  };
  const stepButton = (direction: -1 | 1, buttonLabel: string) => (
    <div
      className="og-icon-button og-slider__step"
      role="button"
      aria-label={buttonLabel}
      onClick={() => {
        playSound(UISound.Press);
        set(value + direction * step);
      }}
    >
      {direction < 0 ? "−" : "+"}
    </div>
  );

  return (
    <div className="og-slider" role="group" aria-label={label}>
      {stepButton(-1, lessLabel)}
      <Focusable
        className="og-slider__track"
        focusClassName="og-focused"
        noFocusRing
        role="slider"
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={value}
        style={{ background: track }}
        onActivate={() => undefined}
        onGamepadDirection={onDirection}
        onClick={onTap}
      >
        <span className="og-slider__thumb" style={{ left: `calc(${((value - min) / span) * 100}% - 6px)`, background: thumb }} />
      </Focusable>
      {stepButton(1, moreLabel)}
    </div>
  );
}
