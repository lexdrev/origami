// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { MONO, SANS, fontFaces } from "./fonts";

// Style B2: amber on graphite, 2 px corners, labels in spaced capitals, numbers in mono.
// Focus is drawn with the og-focused class that Focusable sets on the focused element.

const tokens = `
  --og-panel: #0f1216;
  --og-surface: #13171c;
  --og-divider: #222831;
  --og-border: #2b333d;
  --og-track: #1f252d;
  --og-text: #e8edf2;
  --og-text-soft: #c9d1da;
  --og-muted: #8d98a5;
  --og-dim: #5c6672;
  --og-accent: #ffb020;
  --og-accent-wash: rgba(255, 176, 32, 0.08);
  --og-accent-focus: rgba(255, 176, 32, 0.1);
  --og-danger: #ff6b4a;
  --og-danger-text: #ff8a70;
  --og-danger-wash: rgba(255, 107, 74, 0.07);
  --og-sans: "${SANS}", system-ui, sans-serif;
  --og-mono: "${MONO}", ui-monospace, monospace;
`;

export const styles = `
${fontFaces}

.og-root {
  ${tokens}
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 4px 0 16px;
  color: var(--og-text);
  font-family: var(--og-sans);
  font-size: 13px;
  line-height: 1.3;
}
.og-root *, .og-root *::before, .og-root *::after { box-sizing: border-box; }

.og-screen { display: flex; flex-direction: column; gap: 12px; }

.og-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--og-divider);
}
.og-header__icon { display: flex; color: var(--og-accent); }
.og-header__titles { display: flex; flex-direction: column; gap: 3px; flex-grow: 1; min-width: 0; }
.og-header__title { font-size: 16px; font-weight: 700; letter-spacing: 0.2em; text-transform: uppercase; }
.og-header__title--brand { letter-spacing: 0.22em; }
.og-header__subtitle {
  overflow: hidden;
  color: var(--og-muted);
  font: 500 11px var(--og-mono);
  text-transform: uppercase;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.og-icon-button {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border: 1px solid var(--og-border);
  border-radius: 2px;
  background: var(--og-surface);
  color: var(--og-text);
}
.og-icon-button.og-focused {
  border-color: var(--og-accent);
  background: var(--og-accent-focus);
  color: var(--og-accent);
}

.og-tiles { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.og-tile {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
  min-height: 178px;
  padding: 16px 14px;
  border: 1px solid var(--og-border);
  border-radius: 2px;
  background: var(--og-surface);
}
.og-tile__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border: 1px solid var(--og-border);
  color: var(--og-accent);
}
.og-tile__name { font-size: 13px; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; }
.og-tile__value { font: 700 20px var(--og-mono); text-transform: uppercase; white-space: nowrap; }
.og-tile__sub { margin-top: -6px; color: var(--og-muted); font: 500 11px var(--og-mono); text-transform: uppercase; }

.og-section-label {
  margin-top: 4px;
  margin-bottom: -4px;
  color: var(--og-muted);
  font: 700 11px var(--og-mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.og-choices { display: grid; grid-auto-columns: minmax(0, 1fr); grid-auto-flow: column; gap: 6px; }
.og-choice {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  padding: 0 6px;
  border: 1px solid var(--og-border);
  border-radius: 2px;
  background: var(--og-surface);
  color: var(--og-muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-align: center;
  text-transform: uppercase;
}
.og-choice.og-focused { border-color: var(--og-accent); color: var(--og-text); }
.og-choice--selected { border-color: var(--og-accent); background: var(--og-accent-wash); color: var(--og-accent); }
.og-choice--selected.og-focused { box-shadow: 0 0 0 2px var(--og-panel), 0 0 0 4px var(--og-accent); color: var(--og-accent); }

.og-row {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 40px 10px 12px;
  border: 1px solid var(--og-border);
  border-radius: 2px;
  background: var(--og-surface);
}
.og-row.og-focused { border-color: var(--og-accent); }
.og-row__title { font-size: 12px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; }
.og-row__sub { color: var(--og-muted); font: 500 11px var(--og-mono); text-transform: uppercase; }
.og-row__chevron { position: absolute; top: 50%; right: 12px; display: flex; margin-top: -9px; color: var(--og-dim); }
.og-row.og-focused .og-row__chevron { color: var(--og-accent); }

.og-facts {
  display: grid;
  grid-template-columns: 112px minmax(0, 1fr);
  gap: 6px 8px;
  margin: 0;
  padding: 10px 12px;
  border: 1px solid var(--og-border);
  border-radius: 2px;
  background: var(--og-surface);
  font: 500 11px var(--og-mono);
  text-transform: uppercase;
}
.og-facts__row { display: contents; }
.og-facts dt { color: var(--og-muted); }
.og-facts dd { margin: 0; overflow-wrap: anywhere; }

.og-list {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--og-border);
  border-radius: 2px;
  background: var(--og-surface);
}
.og-list__item {
  padding: 9px 12px;
  border-bottom: 1px solid var(--og-track);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.og-list__item:last-child { border-bottom: 0; }

.og-notice {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--og-border);
  border-radius: 2px;
  background: var(--og-surface);
  color: var(--og-muted);
  font: 500 11px var(--og-mono);
  text-transform: uppercase;
}

.og-alert {
  display: flex;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--og-danger);
  border-radius: 2px;
  background: var(--og-danger-wash);
}
.og-alert__icon { display: flex; flex-shrink: 0; color: var(--og-danger); }
.og-alert__body { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.og-alert__title { color: var(--og-danger-text); font-size: 12px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; }
.og-alert__text { color: var(--og-text-soft); font-size: 12px; line-height: 1.45; overflow-wrap: anywhere; }

.og-about {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 4px;
  padding-top: 12px;
  border-top: 1px solid var(--og-divider);
  color: var(--og-accent);
}
.og-about__lines {
  display: flex;
  flex-direction: column;
  gap: 3px;
  color: var(--og-muted);
  font: 500 11px var(--og-mono);
  text-transform: uppercase;
}
.og-about__name { color: var(--og-text); }
.og-about__name b { letter-spacing: 0.16em; }
`;
