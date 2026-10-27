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
  /** A second line under the label, such as the value a preset sets. */
  detail?: string;
}

interface ChoiceGroupProps<T extends string> {
  label: string;
  choices: readonly Choice<T>[];
  value: T | undefined;
  action: string;
  onChange: (value: T) => void;
  /** Shown after the choices in the same row: a static cell, or a button of its own. */
  after?: ReactNode;
}

export function ChoiceGroup<T extends string>(props: ChoiceGroupProps<T>) {
  const { label, choices, value, action, onChange, after } = props;
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
            className={choiceClass(selected, choice.detail !== undefined)}
            pressed={selected}
            sound={UISound.Press}
            action={action}
            onPress={() => {
              onChange(choice.value);
            }}
          >
            {choice.label}
            {choice.detail !== undefined && <span className="og-choice__detail">{choice.detail}</span>}
          </Pressable>
        );
      })}
      {after}
    </Focusable>
  );
}

export function choiceClass(selected: boolean, twoLines: boolean): string {
  return ["og-choice", twoLines && "og-choice--two-lines", selected && "og-choice--selected"]
    .filter(Boolean)
    .join(" ");
}

export interface Option<T extends string> {
  value: T;
  name: string;
  detail: string;
}

interface OptionListProps<T extends string> {
  label: string;
  options: readonly Option<T>[];
  value: T;
  action: string;
  onChange: (value: T) => void;
}

/** One of several choices that need a line of explanation each, in a column (style B2). */
export function OptionList<T extends string>({ label, options, value, action, onChange }: OptionListProps<T>) {
  return (
    <Focusable className="og-options" role="group" aria-label={label}>
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <Pressable
            key={option.value}
            className={selected ? "og-option og-option--selected" : "og-option"}
            pressed={selected}
            sound={UISound.Press}
            action={action}
            onPress={() => {
              onChange(option.value);
            }}
          >
            <span className="og-option__mark" aria-hidden="true" />
            <span className="og-option__text">
              <span className="og-option__name">{option.name}</span>
              <span className="og-option__detail">{option.detail}</span>
            </span>
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
  /** A grey line under the subtitle about what switching does, problem or not. */
  note?: string;
  onChange: (value: boolean) => void;
}

/** A row with the B2 switch; plays Steam's toggle sounds. */
export function ToggleRow({ title, subtitle, value, action, problem = false, note, onChange }: ToggleRowProps) {
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
      {note !== undefined && <span className="og-row__note">{note}</span>}
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
  /** The subtitle names a problem the next screen fixes (style B2: red frame, triangle and text). */
  problem?: boolean;
  onPress: () => void;
}

/** A row that opens another screen. */
export function NavRow({ title, subtitle, action, problem = false, onPress }: NavRowProps) {
  return (
    <Pressable className={problem ? "og-row og-row--problem" : "og-row"} action={action} onPress={onPress}>
      <span className="og-row__title">{title}</span>
      <span className="og-row__sub">
        {problem && <WarningIcon size={12} />}
        {subtitle}
      </span>
      <span className="og-row__chevron">
        <ChevronIcon />
      </span>
    </Pressable>
  );
}

interface SliderProps {
  label: string;
  /** Shown before the slider, when there are several of them. */
  caption?: string | undefined;
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
  /** A tick on the track at this value, such as the default. */
  notch?: number;
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
  const { label, caption, value, min, max, step, wrap = false, track, thumb, notch, lessLabel, moreLabel, onChange } =
    props;
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
      {caption !== undefined && <span className="og-slider__caption">{caption}</span>}
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
        {notch !== undefined && (
          <span className="og-slider__notch" style={{ left: `${((notch - min) / span) * 100}%` }} />
        )}
        <span className="og-slider__thumb" style={{ left: `calc(${((value - min) / span) * 100}% - 6px)`, background: thumb }} />
      </Focusable>
      {stepButton(1, moreLabel)}
    </div>
  );
}

/** Track background filled with the accent up to the value. */
export function filledTrack(value: number, min: number, max: number): string {
  const fill = `${((value - min) / (max - min)) * 100}%`;
  return `linear-gradient(90deg, var(--og-accent) ${fill}, var(--og-track) ${fill})`;
}
