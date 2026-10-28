// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import type { ReactNode } from "react";

// Folded-paper icons of ORIGAMI. They draw with currentColor; faces filled
// at 16% opacity show the folds.

const FACE_OPACITY = 0.16;

interface IconProps {
  size?: number;
}

const FOX_SILHOUETTE = [
  // Head outline, then ears, eyes and nose cut out with the even-odd rule.
  "M7.52 3 7.92 25.03 9.62 47.57 12.24 49.8 4.25 60.16 50 97 95.75 60.16 87.76 49.8 90.38 47.57",
  "92.08 25.03 92.48 3 54.98 28.83 50 42.33 45.02 28.83Z",
  "M7.52 3 27.32 34.46 19.85 39.32 11.98 19.39Z",
  "M88.02 19.39 80.15 39.32 72.68 34.46 92.48 3Z",
  "M16.83 48.75 38.2 57.01 44.36 73.66 33.22 63.31Z",
  "M83.17 48.75 61.8 57.01 55.64 73.66 66.78 63.31Z",
  "M42.13 85.2 57.87 85.2 50 97Z",
].join(" ");

function Fox({ size }: { size: number | string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true">
      <path d={FOX_SILHOUETTE} fill="currentColor" fillRule="evenodd" />
    </svg>
  );
}

/** The quick access tab's fox for the header and the About block, in the colour around it. */
export function FoxMark({ size = 36 }: IconProps) {
  return <Fox size={size} />;
}

/** Single-colour fox for the Decky plugin list; Steam recolours it for the selected row. */
export function FoxGlyph() {
  return <Fox size="1em" />;
}

function TileIcon({ children }: { children: ReactNode }) {
  return (
    <svg
      width={24}
      height={24}
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.3}
      strokeLinejoin="round"
      strokeLinecap="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

const face = { fill: "currentColor", fillOpacity: FACE_OPACITY } as const;
const open = { fill: "none" } as const;

export function PowerIcon() {
  return (
    <TileIcon>
      <polygon points="14,2 5,13 11,13" {...face} />
      <polygon points="13,11 19,11 10,22" {...face} />
    </TileIcon>
  );
}

export function FansIcon() {
  return (
    <TileIcon>
      <polygon points="12,12 12,2 20,6" {...face} />
      <polygon points="12,12 22,12 18,20" {...open} />
      <polygon points="12,12 12,22 4,18" {...face} />
      <polygon points="12,12 2,12 6,4" {...open} />
    </TileIcon>
  );
}

const SUN_RAYS = [
  [21.2, 7, 22.6, 7],
  [19.97, 4.03, 20.96, 3.04],
  [17, 2.8, 17, 1.4],
  [14.03, 4.03, 13.04, 3.04],
  [19.97, 9.97, 20.96, 10.96],
] as const;

export function DisplayIcon() {
  return (
    <TileIcon>
      <polygon points="1.5,7 17,7 17,17.5 1.5,17.5" {...open} />
      <polygon points="1.5,17.5 17,7 17,17.5" {...face} />
      <polygon points="7.55,17.5 10.95,17.5 11.55,20.5 6.95,20.5" {...open} />
      <line x1={4.95} y1={21} x2={13.55} y2={21} />
      {/* The sun sits on the screen corner; a disc in the background colour interrupts the frame. */}
      <circle cx={17} cy={7} r={4.2} stroke="none" style={{ fill: "var(--og-icon-cutout, var(--og-surface))" }} />
      <circle cx={17} cy={7} r={2.8} {...open} />
      {SUN_RAYS.map(([x1, y1, x2, y2]) => (
        <line key={`${x1}-${y1}`} x1={x1} y1={y1} x2={x2} y2={y2} />
      ))}
    </TileIcon>
  );
}

export function GamepadIcon() {
  return (
    <TileIcon>
      <polygon points="2,15 4,8 9,6 12,6 12,13 9,13 6,18" {...face} />
      <polygon points="22,15 20,8 15,6 12,6 12,13 15,13 18,18" {...open} />
    </TileIcon>
  );
}

export function GearIcon({ size = 20 }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="square"
      aria-hidden="true"
    >
      <circle cx={12} cy={12} r={3.2} />
      <circle cx={12} cy={12} r={7} />
      <path d="M12 2.5v2.4M12 19.1v2.4M2.5 12h2.4M19.1 12h2.4M5.3 5.3l1.7 1.7M17 17l1.7 1.7M5.3 18.7L7 17M17 7l1.7-1.7" />
    </svg>
  );
}

function StrokeIcon({ size, width, d }: { size: number; width: number; d: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={width}
      strokeLinecap="square"
      aria-hidden="true"
    >
      <path d={d} />
    </svg>
  );
}

export const BackIcon = () => <StrokeIcon size={18} width={2.2} d="M15 5l-7 7 7 7" />;
export const UpIcon = () => <StrokeIcon size={14} width={2.4} d="M5 15l7-7 7 7" />;
export const DownIcon = () => <StrokeIcon size={14} width={2.4} d="M5 9l7 7 7-7" />;
export const ChevronIcon = () => <StrokeIcon size={16} width={2.2} d="M9 5l7 7-7 7" />;
export const CheckIcon = () => <StrokeIcon size={12} width={3} d="M4 12l5 5L20 6" />;
export const LockIcon = () => <StrokeIcon size={11} width={2.4} d="M5 11h14v10H5zM8 11V7a4 4 0 0 1 8 0v4" />;

/** A thermometer beside a temperature, in the tile icons' amber. */
export function ThermometerIcon() {
  return (
    <svg width="16" height="24" viewBox="0 0 16 24" fill="none" stroke="currentColor" strokeWidth={1.4} aria-hidden="true">
      <path d="M6 3h4v11.5a4 4 0 1 1-4 0z" strokeLinejoin="round" />
      <path d="M8 8v8" strokeLinecap="square" />
      <circle cx="8" cy="18" r="1.6" fill="currentColor" />
    </svg>
  );
}

/** A filled triangle, as on a play button. */
export function PlayIcon() {
  return (
    <svg width="8" height="10" viewBox="0 0 8 10" aria-hidden="true">
      <path d="M0 0l8 5-8 5z" fill="currentColor" />
    </svg>
  );
}

export function WarningIcon({ size = 16 }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.6}
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 3l10 18H2z" />
      <path d="M12 10v4.5M12 17.5v0.5" />
    </svg>
  );
}
