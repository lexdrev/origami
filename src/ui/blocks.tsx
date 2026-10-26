// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { Focusable, type GamepadEvent } from "@decky/ui";
import type { ReactNode } from "react";

import { useMessages } from "../i18n";
import { IconButton } from "./controls";
import { BackIcon, WarningIcon } from "./icons";

interface ScreenProps {
  /** Goes one screen back; B does the same. The main screen has none. */
  onBack?: () => void;
  children: ReactNode;
}

export function Screen({ onBack, children }: ScreenProps) {
  const t = useMessages();
  if (onBack === undefined) {
    return <div className="og-screen">{children}</div>;
  }
  return (
    <Focusable
      className="og-screen"
      onCancelButton={(event: GamepadEvent) => {
        // Without this Decky would close the whole plugin instead of going one screen back.
        event.stopPropagation();
        onBack();
      }}
      onCancelActionDescription={t.actions.back}
    >
      {children}
    </Focusable>
  );
}

interface HeaderProps {
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  brand?: boolean;
  onBack?: () => void;
  trailing?: ReactNode;
}

export function Header({ title, subtitle, icon, brand = false, onBack, trailing }: HeaderProps) {
  const t = useMessages();
  return (
    <header className="og-header">
      {onBack && (
        <IconButton label={t.actions.back} action={t.actions.back} onPress={onBack}>
          <BackIcon />
        </IconButton>
      )}
      {icon && <span className="og-header__icon">{icon}</span>}
      <span className="og-header__titles">
        <span className={brand ? "og-header__title og-header__title--brand" : "og-header__title"}>{title}</span>
        {subtitle && <span className="og-header__subtitle">{subtitle}</span>}
      </span>
      {trailing}
    </header>
  );
}

interface TileProps {
  icon: ReactNode;
  name: string;
  value: string;
  subtitle: string;
}

export function Tile({ icon, name, value, subtitle }: TileProps) {
  return (
    <div className="og-tile">
      <span className="og-tile__icon">{icon}</span>
      <span className="og-tile__name">{name}</span>
      <span className="og-tile__value">{value}</span>
      <span className="og-tile__sub">{subtitle}</span>
    </div>
  );
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return <span className="og-section-label">{children}</span>;
}

export function FactList({ facts }: { facts: readonly (readonly [string, string])[] }) {
  return (
    <dl className="og-facts">
      {facts.map(([term, value]) => (
        <div key={term} className="og-facts__row">
          <dt>{term}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function List({ items }: { items: readonly string[] }) {
  return (
    <div className="og-list">
      {items.map((item) => (
        <span key={item} className="og-list__item">
          {item}
        </span>
      ))}
    </div>
  );
}

export function Notice({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <div className="og-notice">
      {icon}
      {children}
    </div>
  );
}

/** Red block: something is broken right now (style B2: red means a problem or a conflict). */
export function Alert({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="og-alert" role="alert">
      <span className="og-alert__icon">
        <WarningIcon />
      </span>
      <span className="og-alert__body">
        <span className="og-alert__title">{title}</span>
        <span className="og-alert__text">{children}</span>
      </span>
    </div>
  );
}
