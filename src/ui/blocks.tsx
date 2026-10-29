// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { Focusable, type GamepadEvent } from "@decky/ui";
import type { ReactNode } from "react";

import { useMessages } from "../i18n";
import { ENTER_PREFERRED_CHILD } from "../quickAccess";
import { UISound } from "../sounds";
import { Badge, IconButton, Pressable, Switch } from "./controls";
import { BackIcon, ChevronIcon, WarningIcon } from "./icons";

interface ScreenProps {
  /** Goes one screen back; B does the same. The main screen has none. */
  onBack?: () => void;
  children: ReactNode;
}

export function Screen({ onBack, children }: ScreenProps) {
  const t = useMessages();
  if (onBack === undefined) {
    // Coming into the panel, the focus goes to the child marked preferredFocus, else the first.
    return (
      <Focusable className="og-screen" navEntryPreferPosition={ENTER_PREFERRED_CHILD}>
        {children}
      </Focusable>
    );
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
  subtitle?: string | undefined;
  icon?: ReactNode;
  onBack: () => void;
}

/** Header of a nested screen; the plugin name lives in the Decky title row. */
export function Header({ title, subtitle, icon, onBack }: HeaderProps) {
  const t = useMessages();
  return (
    <header className="og-header">
      <IconButton label={t.actions.back} action={t.actions.back} onPress={onBack}>
        <BackIcon />
      </IconButton>
      {icon && <span className="og-header__icon">{icon}</span>}
      <span className="og-header__titles">
        <span className="og-header__title">{title}</span>
        {subtitle && <span className="og-header__subtitle">{subtitle}</span>}
      </span>
    </header>
  );
}

interface TileProps {
  icon: ReactNode;
  name: string;
  value: string;
  subtitle: string;
  /** Opens the block's screen. */
  onOpen: () => void;
  /** Takes the focus when it comes into the panel. */
  preferredFocus?: boolean;
  /** How many things the block's screen shows red; a red frame and the number beside the arrow. */
  problems?: number | undefined;
}

export function Tile({ icon, name, value, subtitle, onOpen, preferredFocus = false, problems = 0 }: TileProps) {
  const t = useMessages();
  const className = problems > 0 ? "og-tile og-tile--problem" : "og-tile";
  return (
    <Pressable className={className} action={t.actions.open} preferredFocus={preferredFocus} onPress={onOpen}>
      <span className="og-tile__chevron">
        <ChevronIcon />
      </span>
      {problems > 0 && (
        <span className="og-tile__problems">
          <WarningIcon size={12} />
          {problems}
        </span>
      )}
      <span className="og-tile__icon">{icon}</span>
      <span className="og-tile__name">{name}</span>
      <span className="og-tile__value">{value}</span>
      <span className="og-tile__sub">{subtitle}</span>
    </Pressable>
  );
}

interface CardSwitch {
  value: boolean;
  action: string;
  onChange: (value: boolean) => void;
}

/** A framed group of controls with its title, as in the B2 screens; framed amber while focus is inside. */
interface CardProps {
  title?: string;
  /** Beside the title, such as how a game's setting differs from the general one. */
  badge?: string | undefined;
  subtitle?: string | undefined;
  /** The subtitle names a problem the card fixes (style B2: red frame, triangle and text). */
  problem?: boolean;
  aside?: ReactNode;
  /** A switch in the head; while it is off the card is only its head, as every feature with one. */
  toggle?: CardSwitch;
  children: ReactNode;
}

export function Card({ title, badge, subtitle, problem = false, aside, toggle, children }: CardProps) {
  const titles = title && <CardTitles title={title} badge={badge} subtitle={subtitle} problem={problem} />;
  return (
    <section className={problem ? "og-card og-card--problem" : "og-card"}>
      {toggle === undefined ? (
        titles && (
          <div className="og-card__head">
            {titles}
            {aside && <span className="og-card__aside">{aside}</span>}
          </div>
        )
      ) : (
        <SwitchLine title={title ?? ""} badge={badge} subtitle={subtitle} problem={problem} {...toggle} />
      )}
      {toggle === undefined
        ? children
        : toggle.value && (
            <>
              <span className="og-card__divider" aria-hidden="true" />
              {children}
            </>
          )}
    </section>
  );
}

interface SwitchLineProps extends CardSwitch {
  title: string;
  badge?: string | undefined;
  subtitle?: string | undefined;
  problem?: boolean;
}

/** A title with a switch: a card's head, or an option inside a card that has no switch of its own. */
export function SwitchLine({ title, badge, subtitle, problem = false, value, action, onChange }: SwitchLineProps) {
  return (
    <Pressable
      className="og-card__head og-card__head--switch"
      action={action}
      pressed={value}
      sound={value ? UISound.ToggleOff : UISound.ToggleOn}
      onPress={() => {
        onChange(!value);
      }}
    >
      <CardTitles title={title} badge={badge} subtitle={subtitle} problem={problem} />
      <Switch on={value} />
    </Pressable>
  );
}

interface CardTitlesProps {
  title: string;
  badge?: string | undefined;
  subtitle?: string | undefined;
  problem?: boolean;
}

/** A card's title and subtitle; a card without a head places them itself, as the TDP card beside its dial. */
export function CardTitles({ title, badge, subtitle, problem = false }: CardTitlesProps) {
  return (
    <span className="og-card__titles">
      <span className="og-card__title">
        {title}
        {badge !== undefined && <Badge text={badge} />}
      </span>
      {subtitle && (
        <span className="og-card__subtitle">
          {problem && <WarningIcon size={12} />}
          {subtitle}
        </span>
      )}
    </span>
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

interface AlertProps {
  title: string;
  children: ReactNode;
  /** False for a state the user chose, such as Steam setting the TDP: the same block in grey. */
  problem?: boolean;
}

/** Red block: something is broken right now (style B2: red means a problem or a conflict). */
export function Alert({ title, children, problem = true }: AlertProps) {
  return (
    <div className={problem ? "og-alert" : "og-alert og-alert--chosen"} role={problem ? "alert" : undefined}>
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
