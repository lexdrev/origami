// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { MONO, SANS, fontFaces } from "./fonts";

// Style B2 at the real panel size: the Decky plugin area is 300 px wide and has no side
// padding of its own. Amber on graphite, 2 px corners, labels in spaced capitals,
// numbers in mono. Focus is drawn with the og-focused class that Focusable sets.

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
  --og-danger-line: #7a3a2e;
  --og-sans: "${SANS}", system-ui, sans-serif;
  --og-mono: "${MONO}", ui-monospace, monospace;
`;

export const styles = `
${fontFaces}

.og-root, .og-plugin-title {
  ${tokens}
}

.og-root {
  color: var(--og-text);
  font-family: var(--og-sans);
  line-height: 1.3;
}
.og-root *, .og-root *::before, .og-root *::after { box-sizing: border-box; }

.og-root {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0 16px 16px;
  font-size: 12px;
}

.og-screen { display: flex; flex-direction: column; gap: 10px; }

/* ORIGAMI's own tab: Steam's title row laid out like Decky's, and the same gap under it. */
.og-tab-title { display: flex; position: sticky; top: 0; padding-right: 16px; }

/* Fox and name in the title row; flex 0.9 is what Decky gives a plugin name there. */
.og-plugin-title { display: flex; flex: 0.9; align-items: center; gap: 10px; }
.og-plugin-title__icon { display: flex; color: var(--og-accent); }
.og-tab-content { padding-top: 16px; }

.og-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--og-divider);
}
.og-header__icon { display: flex; color: var(--og-accent); }
.og-header__titles { display: flex; flex-direction: column; gap: 3px; flex-grow: 1; min-width: 0; }
.og-header__title { font-size: 14px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; }
.og-header__subtitle { color: var(--og-muted); font: 500 10px/1.35 var(--og-mono); text-transform: uppercase; }

.og-icon-button {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
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

.og-tiles { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.og-tile {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  min-height: 140px;
  padding: 12px;
  border: 1px solid var(--og-border);
  border-radius: 2px;
  background: var(--og-surface);
}
.og-tile.og-focused { border-color: var(--og-accent); }
.og-tile__chevron { position: absolute; top: 12px; right: 10px; display: flex; color: var(--og-dim); }
.og-tile.og-focused .og-tile__chevron { color: var(--og-accent); }
.og-tile__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: 1px solid var(--og-border);
  color: var(--og-accent);
}
.og-tile__name {
  margin-top: 2px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  white-space: nowrap;
}
.og-tile__value { font: 700 17px var(--og-mono); text-transform: uppercase; white-space: nowrap; }
.og-tile__sub {
  margin-top: -4px;
  color: var(--og-muted);
  font: 500 10px/1.35 var(--og-mono);
  text-transform: uppercase;
}

.og-section-label {
  margin-top: 2px;
  margin-bottom: -4px;
  color: var(--og-muted);
  font: 700 10px var(--og-mono);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

/* Choices are one framed strip of cells (draft A); a button beside it, such as a test, is one cell wide. */
.og-choices { display: flex; gap: 6px; }
.og-choices > * { flex: 1 1 0; min-width: 0; }
.og-strip {
  display: grid;
  grid-auto-columns: minmax(0, 1fr);
  grid-auto-flow: column;
  overflow: hidden;
  border: 1px solid var(--og-border);
  border-radius: 2px;
  background: var(--og-surface);
}
.og-choice {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 36px;
  padding: 0 4px;
  border: 1px solid var(--og-border);
  border-radius: 2px;
  background: var(--og-surface);
  color: var(--og-muted);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-align: center;
  text-transform: uppercase;
}
.og-choice--two-lines { flex-direction: column; gap: 2px; height: 46px; }
.og-choice__detail { font: 500 10px var(--og-mono); letter-spacing: 0; }
.og-choice--static { pointer-events: none; }
.og-choice.og-choice--action { gap: 6px; border-style: dashed; border-color: var(--og-dim); background: transparent; color: var(--og-text); }
.og-choice.og-focused { border-color: var(--og-accent); color: var(--og-text); }
.og-strip .og-choice { height: 34px; border: 0; border-left: 1px solid var(--og-border); border-radius: 0; background: transparent; }
.og-strip .og-choice:first-child { border-left: 0; }
.og-strip .og-choice--two-lines { height: 44px; }
.og-strip--dense .og-choice { font-size: 9px; letter-spacing: 0.02em; }
.og-strip .og-choice.og-focused { box-shadow: inset 0 0 0 2px var(--og-accent); }
.og-strip .og-choice--selected { background: rgba(255, 176, 32, 0.12); color: var(--og-accent); box-shadow: inset 0 -2px 0 var(--og-accent); }
.og-strip .og-choice--selected.og-focused { box-shadow: inset 0 0 0 2px var(--og-accent); }

.og-row {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 34px 10px 10px;
  border: 1px solid var(--og-border);
  border-radius: 2px;
  background: var(--og-surface);
}
.og-row.og-focused { border-color: var(--og-accent); }
.og-row__title { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }
.og-row__sub { color: var(--og-muted); font: 500 10px/1.35 var(--og-mono); text-transform: uppercase; }
.og-row__note { color: var(--og-muted); font: 500 10px/1.35 var(--og-mono); text-transform: uppercase; }
.og-row__chevron { position: absolute; top: 50%; right: 10px; display: flex; margin-top: -8px; color: var(--og-dim); }
.og-row.og-focused .og-row__chevron { color: var(--og-accent); }

.og-toggle { padding-right: 58px; }
.og-row--problem { border-color: var(--og-danger-line); }
.og-row--problem .og-row__sub { display: flex; align-items: flex-start; gap: 6px; color: var(--og-danger-text); }
.og-row--problem .og-row__sub svg { flex-shrink: 0; margin-top: 1px; color: var(--og-danger); }
.og-switch {
  position: absolute;
  top: 50%;
  right: 10px;
  width: 38px;
  height: 20px;
  margin-top: -10px;
  border: 1px solid var(--og-border);
  background: var(--og-track);
}
.og-switch__knob { position: absolute; top: 2px; left: 2px; width: 14px; height: 14px; background: var(--og-dim); }
.og-switch--on { border-color: var(--og-accent); background: rgba(255, 176, 32, 0.18); }
.og-switch--on .og-switch__knob { left: 20px; background: var(--og-accent); }

.og-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--og-border);
  border-radius: 2px;
  background: var(--og-surface);
}
.og-card--problem { border-color: var(--og-danger-line); }
.og-card--problem .og-card__subtitle { display: flex; align-items: flex-start; gap: 6px; color: var(--og-danger-text); }
.og-card--problem .og-card__subtitle svg { flex-shrink: 0; margin-top: 1px; color: var(--og-danger); }
.og-card:has(.og-focused) { border-color: var(--og-accent); }
.og-card__head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.og-card__titles { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.og-card__subtitle { color: var(--og-muted); font: 500 10px/1.35 var(--og-mono); text-transform: uppercase; }
.og-card__value { color: var(--og-accent); font: 700 17px var(--og-mono); }
.og-card__label { color: var(--og-muted); font: 700 10px var(--og-mono); letter-spacing: 0.08em; text-transform: uppercase; }
/* A switch in the card head: the card frame shows the focus is inside, a ring that it is on the switch. */
.og-card__head--switch { align-items: center; }
.og-card__head--switch .og-switch { position: relative; top: auto; right: auto; flex-shrink: 0; margin-top: 0; }
.og-card__head--switch.og-focused .og-switch { box-shadow: 0 0 0 2px var(--og-surface), 0 0 0 4px var(--og-accent); }
.og-card__divider { height: 1px; margin: 2px -10px; background: var(--og-divider); }
.og-card__title { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }
.og-card__aside { color: var(--og-muted); font: 500 10px var(--og-mono); text-transform: uppercase; white-space: nowrap; }
.og-card .og-strip { background: var(--og-panel); }

.og-rings { display: flex; justify-content: center; gap: 40px; }
.og-ring { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.og-ring__face { position: relative; width: 64px; height: 64px; }
.og-ring__face > span { position: absolute; border-radius: 50%; }
.og-ring__light { inset: 0; }
.og-ring__gap { inset: 5px; background: var(--og-surface); }
.og-ring__cap { inset: 12px; border: 1px solid var(--og-border); background: #1a1f26; }
.og-ring__label { color: var(--og-muted); font: 500 10px var(--og-mono); text-transform: uppercase; }
.og-ring__label--active { color: var(--og-accent); }
@keyframes og-ring-breath { 0%, 100% { opacity: 1; } 50% { opacity: 0.2; } }
@keyframes og-ring-hue { to { filter: hue-rotate(360deg); } }
@keyframes og-ring-spin { to { transform: rotate(360deg); } }

.og-swatches { display: grid; grid-auto-columns: minmax(0, 1fr); grid-auto-flow: column; gap: 4px; }
.og-swatch { height: 28px; border-radius: 2px; }
.og-swatch--selected { box-shadow: 0 0 0 1px var(--og-surface), 0 0 0 3px var(--og-accent); }
.og-swatch.og-focused { box-shadow: 0 0 0 1px var(--og-surface), 0 0 0 3px var(--og-text); }

.og-slider { display: flex; align-items: center; gap: 8px; }
.og-slider__caption { width: 40px; flex-shrink: 0; color: var(--og-muted); font: 500 10px var(--og-mono); text-transform: uppercase; }
.og-slider__track {
  position: relative;
  flex-grow: 1;
  height: 12px;
  border: 1px solid var(--og-border);
  border-radius: 2px;
}
.og-slider__track.og-focused { border-color: var(--og-accent); box-shadow: 0 0 0 2px var(--og-surface), 0 0 0 3px var(--og-accent); }
.og-slider__notch { position: absolute; top: -4px; width: 2px; height: 18px; margin-left: -1px; background: var(--og-dim); }
.og-slider__thumb {
  position: absolute;
  top: -5px;
  width: 12px;
  height: 20px;
  box-shadow: 0 0 0 2px var(--og-surface);
}
.og-slider__ends {
  display: flex;
  justify-content: space-between;
  margin-top: -2px;
  padding: 0 48px;
  color: var(--og-muted);
  font: 500 9px var(--og-mono);
  text-transform: uppercase;
}
.og-slider__ends--captioned { padding-left: 96px; }
.og-choices__note { margin-top: -4px; color: var(--og-muted); font: 500 10px/1.35 var(--og-mono); text-align: center; text-transform: uppercase; }
.og-card__aside--accent { color: var(--og-accent); }

/* The Power screen's dial: a tick a watt from 7 to 35 W on a 240° arc, every fifth one longer. */
.og-dial {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  border: 1px solid var(--og-border);
  border-radius: 2px;
  background: var(--og-surface);
}
.og-dial__face { position: relative; width: 140px; height: 124px; }
.og-dial__tick { position: absolute; top: 70px; left: 50%; width: 3px; height: 9px; margin: -7px 0 0 -1.5px; background: #262d36; }
.og-dial__tick--major { height: 13px; }
.og-dial__tick--on { background: var(--og-accent); }
.og-dial__tick--drawn { background: var(--og-dim); }
.og-dial__tick--locked { background: transparent; box-shadow: inset 0 0 0 1px #3a434e; }
.og-dial__lock { position: absolute; right: 15px; bottom: 4px; display: flex; color: var(--og-dim); }
.og-dial__center { position: absolute; top: 44px; right: 0; left: 0; display: flex; flex-direction: column; align-items: center; gap: 2px; }
.og-dial__reading { display: flex; align-items: baseline; gap: 4px; }
.og-dial__value { font: 700 36px/1 var(--og-mono); }
.og-dial__unit { color: var(--og-muted); font: 500 12px var(--og-mono); text-transform: uppercase; }
.og-dial__label { color: var(--og-muted); font: 500 9px var(--og-mono); text-transform: uppercase; white-space: nowrap; }
.og-dial__end { position: absolute; bottom: 4px; color: var(--og-muted); font: 500 9px var(--og-mono); }
.og-dial__end--low { left: 4px; }
.og-dial__end--high { right: 0; }
.og-dial__readout {
  display: flex;
  justify-content: center;
  gap: 8px;
  width: 100%;
  color: var(--og-muted);
  font: 500 10px var(--og-mono);
  text-transform: uppercase;
  white-space: nowrap;
}
.og-dial__readout--split { justify-content: space-between; }
.og-dial__readout b { color: var(--og-text); }
.og-dial__status { display: flex; align-items: center; gap: 5px; }
.og-dial__status::before { content: ""; width: 7px; height: 7px; background: var(--og-dim); }
.og-dial__status--problem { color: var(--og-danger-text); }
.og-dial__status--problem::before { background: var(--og-danger); }

.og-limits { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 5px; }
.og-limit { display: flex; flex-direction: column; gap: 2px; padding: 6px 7px; border: 1px solid var(--og-track); background: var(--og-panel); }
.og-limit__value { font: 700 13px var(--og-mono); text-transform: uppercase; white-space: nowrap; }
.og-limit__value--boost { color: var(--og-accent); }
.og-limit__code { font: 500 9px var(--og-mono); }
.og-limit__label { color: var(--og-muted); font: 500 9px var(--og-mono); text-transform: uppercase; }

.og-battery {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 2px 0;
  border-top: 1px solid var(--og-divider);
  color: var(--og-muted);
  font: 500 10px var(--og-mono);
  text-transform: uppercase;
}
.og-battery b { color: var(--og-text); }

.og-colour-value { display: flex; align-items: center; justify-content: center; gap: 10px; padding-top: 8px; border-top: 1px solid var(--og-border); }
.og-colour-value__swatch { width: 18px; height: 18px; border-radius: 2px; }
.og-colour-value__hex { font: 700 16px var(--og-mono); }

.og-note { padding: 10px; border: 1px solid var(--og-border); border-radius: 2px; color: var(--og-text-soft); font-size: 11px; line-height: 1.45; }

.og-options { display: flex; flex-direction: column; gap: 5px; }
.og-option { display: flex; align-items: center; gap: 10px; padding: 7px 10px; border: 1px solid var(--og-border); border-radius: 2px; background: var(--og-surface); }
.og-option.og-focused { border-color: var(--og-accent); }
.og-option--selected { border-color: var(--og-accent); background: rgba(255, 176, 32, 0.06); }
.og-option--selected.og-focused { box-shadow: 0 0 0 2px var(--og-panel), 0 0 0 4px var(--og-accent); }
.og-option__mark { display: flex; align-items: center; justify-content: center; width: 14px; height: 14px; flex-shrink: 0; box-sizing: border-box; border: 1px solid var(--og-dim); }
.og-option--selected .og-option__mark { border-color: var(--og-accent); }
.og-option--selected .og-option__mark::after { content: ""; width: 6px; height: 6px; background: var(--og-accent); }
.og-option__text { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.og-option__name { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }
.og-option--selected .og-option__name { color: var(--og-accent); }
.og-option__detail { color: var(--og-muted); font: 500 10px/1.35 var(--og-mono); text-transform: uppercase; }

.og-column { display: flex; flex-direction: column; gap: 6px; }
.og-column__item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 0 6px 0 10px;
  border: 1px solid var(--og-border);
  border-radius: 2px;
  background: var(--og-surface);
  color: var(--og-muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.og-column__item--own { border-color: var(--og-accent); background: rgba(255, 176, 32, 0.06); color: var(--og-accent); }
.og-column__number { width: 14px; color: var(--og-dim); font: 500 10px var(--og-mono); }
.og-column__name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.og-column__item .og-icon-button { width: 30px; height: 28px; }

.og-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }
.og-button {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 36px;
  border: 1px solid var(--og-border);
  border-radius: 2px;
  background: var(--og-surface);
  color: var(--og-text);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.og-button.og-focused { border-color: var(--og-accent); color: var(--og-accent); }
.og-button.og-button--primary { border-color: var(--og-accent); background: var(--og-accent); color: #14100a; }
.og-button.og-button--primary.og-focused { color: #14100a; box-shadow: 0 0 0 2px var(--og-panel), 0 0 0 4px var(--og-accent); }

.og-disabled { opacity: 0.4; }

.og-hint { margin-top: -4px; color: var(--og-muted); font-size: 11px; line-height: 1.45; }

.og-facts {
  display: grid;
  grid-template-columns: 90px minmax(0, 1fr);
  gap: 6px 8px;
  margin: 0;
  padding: 10px;
  border: 1px solid var(--og-border);
  border-radius: 2px;
  background: var(--og-surface);
  font: 500 10px var(--og-mono);
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
  padding: 8px 10px;
  border-bottom: 1px solid var(--og-track);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.og-list__item:last-child { border-bottom: 0; }

.og-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--og-border);
  border-radius: 2px;
  background: var(--og-surface);
  color: var(--og-muted);
  font: 500 10px var(--og-mono);
  text-transform: uppercase;
}

.og-alert {
  display: flex;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--og-danger);
  border-radius: 2px;
  background: var(--og-danger-wash);
}
.og-alert__icon { display: flex; flex-shrink: 0; color: var(--og-danger); }
.og-alert__body { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.og-alert__title { color: var(--og-danger-text); font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
.og-alert__text { color: var(--og-text-soft); font-size: 11px; line-height: 1.45; overflow-wrap: anywhere; }

.og-about {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 2px;
  padding-top: 10px;
  border-top: 1px solid var(--og-divider);
  color: var(--og-accent);
}
.og-about__lines {
  display: flex;
  flex-direction: column;
  gap: 3px;
  color: var(--og-muted);
  font: 500 10px var(--og-mono);
  text-transform: uppercase;
}
.og-about__name { color: var(--og-text); }
.og-about__name b { letter-spacing: 0.16em; }
`;
