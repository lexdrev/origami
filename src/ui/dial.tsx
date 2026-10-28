// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { MAX_TDP, MIN_TDP } from "../power";
import { LockIcon } from "./icons";

// The Power screen's dial (style B2): one tick a watt from 7 to 35 W on a 240° arc, every fifth
// one longer, lit up to the value. It only shows; the TDP is set in the card under it. The arc
// keeps its watts in place: those the battery does not allow stay on it as empty, locked ticks.

const ARC_DEGREES = 240;
const TICKS = MAX_TDP - MIN_TDP + 1;

export type DialFill = "on" | "drawn";

export interface DialStatus {
  text: string;
  problem: boolean;
}

interface DialProps {
  value: string;
  unit: string;
  label: string;
  /** Watts the arc is lit up to, and how. */
  fill: { watts: number; kind: DialFill };
  /** The watts over this are locked: on the battery, until more than 25 W is allowed. */
  locked?: number | undefined;
  /** The power drawn now, under the dial; absent where the dial shows it itself. */
  now?: { label: string; value: string } | undefined;
  status?: DialStatus | null | undefined;
}

export function Dial({ value, unit, label, fill, locked, now, status }: DialProps) {
  return (
    <div className="og-dial">
      <div className="og-dial__face" aria-hidden="true">
        {Array.from({ length: TICKS }, (_, index) => {
          const watts = MIN_TDP + index;
          const angle = -ARC_DEGREES / 2 + index * (ARC_DEGREES / (TICKS - 1));
          const kind = locked !== undefined && watts > locked ? "locked" : watts <= fill.watts ? fill.kind : null;
          const classes = ["og-dial__tick", watts % 5 === 0 && "og-dial__tick--major", kind && `og-dial__tick--${kind}`];
          return (
            <span
              key={watts}
              className={classes.filter(Boolean).join(" ")}
              style={{ transform: `rotate(${angle.toFixed(2)}deg) translateY(-56px)` }}
            />
          );
        })}
        <span className="og-dial__center">
          <span className="og-dial__reading">
            <span className="og-dial__value">{value}</span>
            <span className="og-dial__unit">{unit}</span>
          </span>
          <span className="og-dial__label">{label}</span>
        </span>
        <span className="og-dial__end og-dial__end--low">{MIN_TDP}</span>
        <span className="og-dial__end og-dial__end--high">{MAX_TDP}</span>
        {locked !== undefined && (
          <span className="og-dial__lock">
            <LockIcon />
          </span>
        )}
      </div>
      {now !== undefined && (
        <div className={status ? "og-dial__readout og-dial__readout--split" : "og-dial__readout"}>
          <span>
            {now.label} <b>{now.value}</b>
          </span>
          {status && (
            <span className={status.problem ? "og-dial__status og-dial__status--problem" : "og-dial__status"}>
              {status.text}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
