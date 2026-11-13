// SPDX-FileCopyrightText: 2026 Alexander Derevyanko (lexdrev)
// SPDX-License-Identifier: GPL-3.0-or-later

import { useEffect, useState } from "react";

import type { FanCurve, Telemetry } from "../backend";
import { fanHistory } from "../fanHistory";
import {
  curveName,
  curveSteps,
  DEFAULT_FAN_CURVE,
  FAN_PRESETS,
  FAN_STEP,
  FAN_TEMPS,
  heldTarget,
  HOLD_TARGETS,
  holdState,
  movePoint,
  ownCurve,
  presetOf,
  speedNow,
  type CurvePoint,
} from "../fans";
import { useMessages } from "../i18n";
import { formatNumber, withUnit } from "../i18n/format";
import { back } from "../navigation";
import { conflicts, refreshConflicts, setFans, settings } from "../state";
import { useStore } from "../store";
import { Card, Header, Screen } from "../ui/blocks";
import { ChoiceGroup, filledTrack, Slider } from "../ui/controls";
import { ThermometerIcon } from "../ui/icons";
import { useTelemetry } from "../useTelemetry";
import { LoadFailed } from "./LoadFailed";
import { OwnedBy } from "./OwnedBy";

type FanReadings = Telemetry["fans"];

/** Top of the speed gauges: the fans' full speed on the Ally X, 8000 and 8200 rpm as measured. */
const GAUGE_RPM = 8000;
const GAUGE_TICKS = 25;
const GAUGE_DEGREES = 240;
/** The picked point when the screen opens: 60 °C, where games spend most of the time. */
const FIRST_POINT = 3;

export function FansScreen() {
  const t = useMessages();
  const current = useStore(settings);
  const owners = useStore(conflicts);
  const readings = useTelemetry();

  useEffect(() => {
    void refreshConflicts();
  }, []);

  const fans = readings.status === "ready" ? readings.value.fans : null;
  const owner = owners.status === "ready" ? owners.value.fans : null;
  return (
    <Screen onBack={back}>
      <Header onBack={back} title={t.fans.title} />
      <FanCards fans={fans} />
      <Temperatures fans={fans} />
      <LoadFailed loads={[current, owners]} />
      {current.status === "ready" &&
        owners.status === "ready" &&
        (owner !== null ? (
          <OwnedBy title={t.fans.ownedBy(owner)} text={t.fans.ownedText(owner)} />
        ) : (
          <CurveCard curve={current.value.fans} fans={fans} />
        ))}
    </Screen>
  );
}

function hottestOf(fans: FanReadings | null): number | null {
  const temps = [fans?.cpuTempC, fans?.gpuTempC].filter((temp) => temp != null);
  return temps.length > 0 ? Math.max(...temps) : null;
}

/** Both fans' speeds now on gauges, with their last minute under each. */
function FanCards({ fans }: { fans: FanReadings | null }) {
  const t = useMessages();
  const history = useStore(fanHistory);
  return (
    <div className="og-pair">
      {t.fans.fans.map((name, fan) => {
        const rpm = fans?.speedsRpm[fan] ?? null;
        return (
          <div key={name} className="og-fan">
            <FanGauge rpm={rpm} />
            <span className="og-fan__name">{name}</span>
            <span className="og-fan__part">{t.fans.parts[fan]}</span>
            <Sparkline samples={history[fan] ?? []} label={t.fans.history(name)} />
            <span className="og-fan__ends">
              <span>{t.fans.minuteAgo}</span>
              <span>{t.fans.now}</span>
            </span>
          </div>
        );
      })}
    </div>
  );
}

function FanGauge({ rpm }: { rpm: number | null }) {
  const t = useMessages();
  return (
    <div className="og-fan__gauge" aria-hidden="true">
      {Array.from({ length: GAUGE_TICKS }, (_, index) => {
        const angle = -GAUGE_DEGREES / 2 + index * (GAUGE_DEGREES / (GAUGE_TICKS - 1));
        const lit = rpm !== null && (index / (GAUGE_TICKS - 1)) * GAUGE_RPM <= rpm && rpm > 0;
        const classes = ["og-fan__tick", index % 6 === 0 && "og-fan__tick--major", lit && "og-fan__tick--on"];
        return (
          <span
            key={index}
            className={classes.filter(Boolean).join(" ")}
            style={{ transform: `rotate(${angle.toFixed(2)}deg) translateY(-42px)` }}
          />
        );
      })}
      <span className="og-fan__reading">
        <span className="og-fan__rpm">{rpm === null ? t.unknown : formatNumber(rpm, t.locale)}</span>
        <span className="og-fan__unit">{t.units.rpm}</span>
      </span>
    </div>
  );
}

const SPARK_WIDTH = 108;
const SPARK_HEIGHT = 30;
const SPARK_SAMPLES = 60;
/** The graph spans at least this many rpm around the middle of the minute, so a fan's wobble of a few
 * hundred rpm stays a ripple and a steady fan a line across the middle. */
const SPARK_SPAN = 2000;

function Sparkline({ samples, label }: { samples: readonly number[]; label: string }) {
  const middle = (Math.min(...samples) + Math.max(...samples)) / 2;
  const span = Math.max(SPARK_SPAN, Math.max(...samples) - Math.min(...samples));
  const low = middle - span / 2;
  const high = middle + span / 2;
  const step = SPARK_WIDTH / (SPARK_SAMPLES - 1);
  const points = samples
    .map((rpm, index) => {
      const x = SPARK_WIDTH - (samples.length - 1 - index) * step;
      const y = SPARK_HEIGHT - 2 - ((rpm - low) / (high - low)) * (SPARK_HEIGHT - 4);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg className="og-fan__spark" viewBox={`0 0 ${SPARK_WIDTH} ${SPARK_HEIGHT}`} role="img" aria-label={label}>
      <line className="og-fan__base" x1="0" y1={SPARK_HEIGHT - 1} x2={SPARK_WIDTH} y2={SPARK_HEIGHT - 1} />
      {samples.length > 1 && <polyline className="og-fan__line" points={points} />}
    </svg>
  );
}

function Temperatures({ fans }: { fans: FanReadings | null }) {
  const t = useMessages();
  const temps = [fans?.cpuTempC ?? null, fans?.gpuTempC ?? null];
  return (
    <div className="og-pair">
      {t.fans.temperatures.map((name, index) => {
        const temp = temps[index] ?? null;
        return (
          <div key={name} className="og-temp">
            <ThermometerIcon />
            <span className="og-temp__text">
              <span className="og-temp__value">{temp === null ? t.unknown : `${formatNumber(temp, t.locale)}°`}</span>
              <span className="og-temp__name">{name}</span>
            </span>
          </div>
        );
      })}
    </div>
  );
}

const percent = (value: number) => `${value}%`;

/**
 * What runs both fans: the switch in the head, and while it is on the choice between the curve and
 * a temperature to hold, each with the curve the firmware follows and the temperature now on it.
 */
function CurveCard({ curve, fans }: { curve: FanCurve | null; fans: FanReadings | null }) {
  const t = useMessages();
  const current = curve ?? DEFAULT_FAN_CURVE;
  const on = curve?.enabled ?? false;
  const hottest = hottestOf(fans);
  const rpm = fans?.speedsRpm[0] ?? null;
  const held = fans?.holdCurve ?? null;
  const state = held !== null && hottest !== null ? holdState(held, current.target, hottest) : "holding";
  const target = heldTarget(curve);
  const subtitle = current.hold
    ? t.fans.holdSubs[state]
    : t.fans.curveSubs[presetOf(current.points)?.id ?? "custom"];
  return (
    <Card
      title={
        target !== null
          ? t.fans.holds(withUnit(String(target), t.units.celsius))
          : t.fans.curve(curveName(curve, t))
      }
      subtitle={on ? subtitle : t.fans.curveOff}
      toggle={{
        value: on,
        action: t.actions.toggle,
        onChange: (enabled) => {
          setFans({ ...current, enabled });
        },
      }}
    >
      <span className="og-card__label">{t.fans.mode}</span>
      <ChoiceGroup
        label={t.fans.mode}
        choices={[
          { value: "curve", label: t.fans.modes.curve },
          { value: "hold", label: t.fans.modes.hold },
        ]}
        value={current.hold ? "hold" : "curve"}
        action={t.actions.select}
        onChange={(mode) => {
          setFans({ ...current, enabled: true, hold: mode === "hold" });
        }}
      />
      {current.hold ? (
        <HoldSettings curve={current} held={held} hottest={hottest} rpm={rpm} full={state === "full"} />
      ) : (
        <CurveSettings curve={current} hottest={hottest} rpm={rpm} />
      )}
    </Card>
  );
}

/** The user's own curve: the presets with the custom curve last, and the point picked with its speed. */
interface CurveSettingsProps {
  curve: FanCurve;
  hottest: number | null;
  /** Fan 1 now: it tells the step the fans are on. */
  rpm: number | null;
}

function CurveSettings({ curve, hottest, rpm }: CurveSettingsProps) {
  const t = useMessages();
  const [point, setPoint] = useState(FIRST_POINT);
  const { points } = curve;
  const preset = presetOf(points);
  const speed = points[point] ?? 0;
  const now = hottest === null ? null : speedNow(ownCurve(points), hottest, rpm);
  const temp = (value: number) => withUnit(String(value), t.units.celsius);
  return (
    <>
      {hottest !== null && now !== null && (
        <span className="og-card__label">
          {t.fans.speedNow(temp(Math.round(hottest)), percent(now))}
        </span>
      )}
      <CurveChart curve={ownCurve(points)} picked={point} hottest={hottest} speed={now} />
      <span className="og-card__label">{t.fans.preset}</span>
      <ChoiceGroup
        label={t.fans.preset}
        choices={FAN_PRESETS.map((choice) => ({ value: choice.id, label: t.fans.presets[choice.id] }))}
        value={preset?.id}
        action={t.actions.select}
        onChange={(id) => {
          const choice = FAN_PRESETS.find((candidate) => candidate.id === id);
          if (choice !== undefined) setFans({ ...curve, enabled: true, points: [...choice.points] });
        }}
        custom={{ label: t.fans.presets.custom, selected: preset === undefined }}
      />
      <span className="og-card__label">{t.fans.point}</span>
      <ChoiceGroup
        label={t.fans.point}
        choices={FAN_TEMPS.map((at, index) => ({
          value: String(index),
          label: `${at}°`,
          detail: percent(points[index] ?? 0),
        }))}
        value={String(point)}
        action={t.actions.select}
        onChange={(index) => {
          setPoint(Number(index));
        }}
      />
      <div className="og-card__head">
        <span className="og-card__label">{t.fans.speedAt(temp(FAN_TEMPS[point] ?? 0))}</span>
        <span className="og-card__value">{percent(speed)}</span>
      </div>
      <Slider
        label={t.fans.speedAt(temp(FAN_TEMPS[point] ?? 0))}
        value={speed}
        min={0}
        max={100}
        step={FAN_STEP}
        track={filledTrack(speed, 0, 100)}
        thumb="var(--og-accent)"
        lessLabel={t.actions.less}
        moreLabel={t.actions.more}
        onChange={(value) => {
          setFans({ ...curve, enabled: true, points: movePoint(points, point, value) });
        }}
      />
      <span className="og-choices__note">{t.fans.safety}</span>
    </>
  );
}

interface HoldSettingsProps {
  curve: FanCurve;
  /** The curve the backend keeps in the firmware; null until the readings bring it. */
  held: readonly CurvePoint[] | null;
  hottest: number | null;
  rpm: number | null;
  /** The fans run at full speed and the chip is still warmer than asked. */
  full: boolean;
}

/** A temperature to hold: the curve the firmware follows now, and the target on a slider. */
function HoldSettings({ curve, held, hottest, rpm, full }: HoldSettingsProps) {
  const t = useMessages();
  const now = held === null || hottest === null ? null : speedNow(held, hottest, rpm);
  const temp = (value: number) => withUnit(String(value), t.units.celsius);
  return (
    <>
      {hottest !== null && (
        <span className="og-card__label">
          {t.fans.speedNow(temp(Math.round(hottest)), now === null ? t.unknown : percent(now))}
        </span>
      )}
      <CurveChart curve={held ?? []} picked={null} hottest={hottest} speed={now} target={curve.target} />
      <div className="og-card__head">
        <span className="og-card__label">{t.fans.target}</span>
        <span className="og-card__value">{temp(curve.target)}</span>
      </div>
      <Slider
        label={t.fans.target}
        value={curve.target}
        min={HOLD_TARGETS.min}
        max={HOLD_TARGETS.max}
        step={1}
        track={filledTrack(curve.target, HOLD_TARGETS.min, HOLD_TARGETS.max)}
        thumb="var(--og-accent)"
        lessLabel={t.actions.less}
        moreLabel={t.actions.more}
        onChange={(target) => {
          setFans({ ...curve, enabled: true, target });
        }}
      />
      <span className="og-choices__note">{full ? t.fans.holdFull : t.fans.holdNote}</span>
    </>
  );
}

// The chart's frame in its own units: the speed scale on the left, the temperatures under it.
const CHART = { width: 242, height: 128, left: 26, right: 238, top: 8, bottom: 108 } as const;
const CHART_TEMPS = { low: 30, high: 100 } as const;
const SPEED_LINES = [100, 75, 50, 25, 0] as const;

const chartX = (temp: number) =>
  CHART.left + ((temp - CHART_TEMPS.low) * (CHART.right - CHART.left)) / (CHART_TEMPS.high - CHART_TEMPS.low);
const chartY = (speed: number) => CHART.bottom - (speed * (CHART.bottom - CHART.top)) / 100;
const chartPoints = (curve: readonly CurvePoint[]) =>
  curve.map(([temp, speed]) => `${chartX(temp).toFixed(1)},${chartY(speed).toFixed(1)}`).join(" ");

interface CurveChartProps {
  /** The eight points the firmware follows; none draws the empty frame. */
  curve: readonly CurvePoint[];
  /** The user's point picked for the slider; null for a curve that has no points to set. */
  picked: number | null;
  hottest: number | null;
  /** The speed the fans run at now, in percent: the dot's height. */
  speed: number | null;
  /** The temperature held, marked on the chart. */
  target?: number;
}

/**
 * The curve the firmware follows, in the steps it takes, and where the temperature and the fans are
 * now: the dot stands off the line while the fans still keep the step above.
 * The user's curve shows its seven points with the picked one marked, and the step to full speed at
 * 100 °C dashed as not theirs; a curve that holds a temperature is one line with the target marked.
 */
function CurveChart({ curve, picked, hottest, speed, target }: CurveChartProps) {
  const t = useMessages();
  const own = picked !== null;
  const steps = curveSteps(curve);
  // The last point's two steps are the firmware's own: up to 100 °C, and full speed there.
  const line = own ? steps.slice(0, -2) : steps;
  const now = hottest === null ? null : Math.min(CHART_TEMPS.high, Math.max(CHART_TEMPS.low, hottest));
  return (
    <svg className="og-curve" viewBox={`0 0 ${CHART.width} ${CHART.height}`} role="img" aria-label={t.fans.chart}>
      {SPEED_LINES.map((speed) => (
        <g key={speed}>
          <line
            className={speed === 0 ? "og-curve__axis" : "og-curve__grid"}
            x1={CHART.left}
            y1={chartY(speed)}
            x2={CHART.right}
            y2={chartY(speed)}
          />
          <text className="og-curve__scale" x={CHART.left - 5} y={chartY(speed) + 4} textAnchor="end">
            {speed}
          </text>
        </g>
      ))}
      {FAN_TEMPS.map((temp) => (
        <g key={temp}>
          <line className="og-curve__grid" x1={chartX(temp)} y1={CHART.top} x2={chartX(temp)} y2={CHART.bottom} />
          <text className="og-curve__scale" x={chartX(temp)} y={CHART.height - 4} textAnchor="middle">
            {temp}°
          </text>
        </g>
      ))}
      {target !== undefined && (
        <line className="og-curve__target" x1={chartX(target)} y1={CHART.top} x2={chartX(target)} y2={CHART.bottom} />
      )}
      {now !== null && (
        <line className="og-curve__now" x1={chartX(now)} y1={CHART.top} x2={chartX(now)} y2={CHART.bottom} />
      )}
      <polyline className="og-curve__line" points={chartPoints(line)} />
      {own && <polyline className="og-curve__tail" points={chartPoints(steps.slice(-3))} />}
      {own &&
        curve.slice(0, FAN_TEMPS.length).map(([temp, speed], index) => {
          const size = index === picked ? 12 : 9;
          return (
            <rect
              key={temp}
              className={index === picked ? "og-curve__point og-curve__point--picked" : "og-curve__point"}
              x={chartX(temp) - size / 2}
              y={chartY(speed) - size / 2}
              width={size}
              height={size}
            />
          );
        })}
      {now !== null && speed !== null && (
        <circle className="og-curve__dot" cx={chartX(now)} cy={chartY(speed)} r="5" />
      )}
    </svg>
  );
}
