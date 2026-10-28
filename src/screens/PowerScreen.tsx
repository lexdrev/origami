// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { useEffect } from "react";

import type { BatteryTelemetry, Limits, Power, Settings, Telemetry } from "../backend";
import { useMessages } from "../i18n";
import { formatNumber, withUnit } from "../i18n/format";
import { back } from "../navigation";
import {
  BATTERY_TDP,
  batteryTexts,
  formatWatts,
  limitsFor,
  MAX_TDP,
  MIN_TDP,
  presetOf,
  steamTdpSlider,
  TDP_PRESETS,
  TDP_STEP,
} from "../power";
import { mainWindow, QuickAccessTab, steamTab } from "../quickAccess";
import { UISound } from "../sounds";
import { conflicts, heldPower, refreshConflicts, setPower, updateSettings } from "../state";
import { settings } from "../state";
import { useStore } from "../store";
import { Alert, Card, CardTitles, Header, Screen } from "../ui/blocks";
import { ChoiceGroup, filledTrack, Pressable, Slider, ToggleRow } from "../ui/controls";
import { Dial, DialFace, DialReadout, type DialStatus } from "../ui/dial";
import { useTelemetry } from "../useTelemetry";
import { OwnedBy } from "./OwnedBy";

/** Drawing less than this share of the limit, the SoC has nothing to do that needs it. */
const NO_LOAD_SHARE = 0.5;

type PowerReadings = Telemetry["power"];

export function PowerScreen() {
  const t = useMessages();
  const current = useStore(settings);
  const owners = useStore(conflicts);
  const readings = useTelemetry();

  useEffect(() => {
    void refreshConflicts();
  }, []);

  if (current.status !== "ready" || owners.status !== "ready") {
    return (
      <Screen onBack={back}>
        <Header onBack={back} title={t.power.title} />
      </Screen>
    );
  }
  const power = readings.status === "ready" ? readings.value.power : null;
  const owner = owners.value.power;
  return (
    <Screen onBack={back}>
      <Header onBack={back} title={t.power.title} />
      {owner !== null ? (
        <>
          <DrawnDial power={power} />
          <OwnedBy title={t.power.ownedBy(owner)} text={t.power.ownedText(owner)} />
        </>
      ) : current.value.manageTdp ? (
        <OwnPower setting={current.value} power={power} />
      ) : (
        <>
          <DrawnDial power={power} />
          <Alert title={t.power.steamSets}>{t.power.steamSetsText}</Alert>
          <BoostRow power={current.value.power} readings={power} />
        </>
      )}
      {power?.battery && <BatteryLine battery={power.battery} />}
    </Screen>
  );
}

/** ORIGAMI holds the TDP: the TDP card with its dial, then the headroom and the switches. */
function OwnPower({ setting, power }: { setting: Settings; power: PowerReadings | null }) {
  const t = useMessages();
  const held = useStore(heldPower);
  const steamSlider = useStore(steamTdpSlider) === true;
  const holding = held.status === "ready" ? held.value : null;
  const heldLimits = holding?.limits ?? null;
  const highest = highestTdp(power, setting.batteryHighTdp);
  // A TDP chosen on the charger stays; on the battery the screen shows the 25 W held.
  const shown = Math.min(setting.power.tdp, highest);
  const limits = heldLimits?.spl === shown ? heldLimits : limitsFor({ ...setting.power, tdp: shown });
  const drawn = power?.packagePowerW ?? null;
  const status: DialStatus | null = steamSlider
    ? { text: t.power.steamSliderIdle, problem: true }
    : holding?.contested
      ? { text: t.power.contested, problem: true }
      : drawn !== null && drawn < shown * NO_LOAD_SHARE
        ? { text: t.power.noLoad, problem: false }
        : null;

  return (
    <>
      {steamSlider && <SteamSliderPlate />}
      {holding?.contested && <Alert title={t.power.contested}>{t.power.contestedText}</Alert>}
      <TdpCard power={setting.power} highest={highest} drawn={drawn} status={status} />
      <HeadroomCard power={setting.power} limits={limits} />
      <BoostRow power={setting.power} readings={power} />
      <ToggleRow
        title={t.power.batteryHigh}
        subtitle={setting.batteryHighTdp ? t.power.batteryHighOn : t.power.batteryHighOff}
        value={setting.batteryHighTdp}
        action={t.actions.toggle}
        onChange={(batteryHighTdp) => void updateSettings({ batteryHighTdp })}
      />
    </>
  );
}

/** The top of the TDP scale: 35 W on the charger, and on the battery only once allowed. */
function highestTdp(power: PowerReadings | null, batteryHighTdp: boolean): number {
  return power?.onBattery === true && !batteryHighTdp ? BATTERY_TDP : MAX_TDP;
}

/** The power drawn now on the dial, where ORIGAMI does not set the TDP. */
function DrawnDial({ power }: { power: PowerReadings | null }) {
  const t = useMessages();
  const drawn = power?.packagePowerW ?? null;
  return (
    <Dial
      value={drawn === null ? t.unknown : formatNumber(drawn, t.locale, 1)}
      unit={t.units.watts}
      label={t.power.now}
      fill={{ watts: drawn ?? 0, kind: "drawn" }}
    />
  );
}

interface TdpCardProps {
  power: Power;
  highest: number;
  drawn: number | null;
  status: DialStatus | null;
}

/**
 * The sustained limit in one card: the dial with the title and the power drawn beside it, then the
 * scale up to its top and the presets, as the saturation. The dial shows the scale's ends.
 */
function TdpCard({ power, highest, drawn, status }: TdpCardProps) {
  const t = useMessages();
  const tdp = Math.min(power.tdp, highest);
  const preset = presetOf(tdp);
  const watts = (value: number) => withUnit(String(value), t.units.watts);
  return (
    <Card>
      <div className="og-tdp">
        <DialFace
          value={String(tdp)}
          unit={t.units.watts}
          label={t.power.limit}
          fill={{ watts: tdp, kind: "on" }}
          locked={highest < MAX_TDP ? highest : undefined}
        />
        <div className="og-tdp__side">
          <CardTitles title={t.power.tdp} subtitle={t.power.tdpSub} />
          {drawn !== null && <DialReadout now={{ label: t.power.now, value: formatWatts(drawn, t) }} status={status} />}
        </div>
      </div>
      <Slider
        label={t.power.tdp}
        value={tdp}
        min={MIN_TDP}
        max={highest}
        step={TDP_STEP}
        track={filledTrack(tdp, MIN_TDP, highest)}
        thumb="var(--og-accent)"
        lessLabel={t.actions.less}
        moreLabel={t.actions.more}
        onChange={(tdp) => {
          setPower({ ...power, tdp });
        }}
      />
      <ChoiceGroup
        label={t.power.tdp}
        choices={TDP_PRESETS.map((choice) => ({
          value: choice.id,
          label: t.power.presets[choice.id],
          detail: watts(choice.watts),
        }))}
        value={preset?.id}
        action={t.actions.select}
        onChange={(id) => {
          const choice = TDP_PRESETS.find((candidate) => candidate.id === id);
          if (choice !== undefined) setPower({ ...power, tdp: choice.watts });
        }}
        custom={{
          label: t.power.presets.custom,
          detail: preset === undefined ? watts(tdp) : "+",
          selected: preset === undefined,
        }}
      />
    </Card>
  );
}

/** Short boosts over the TDP: the switch in the head, the three limits inside while it is on. */
function HeadroomCard({ power, limits }: { power: Power; limits: Limits }) {
  const t = useMessages();
  return (
    <Card
      title={t.power.headroom}
      subtitle={power.headroom ? t.power.headroomOn : t.power.headroomOff}
      toggle={{
        value: power.headroom,
        action: t.actions.toggle,
        onChange: (headroom) => {
          setPower({ ...power, headroom });
        },
      }}
    >
      <div className="og-limits">
        {(["spl", "sppt", "fppt"] as const).map((key) => (
          <span key={key} className="og-limit">
            <span className={key === "spl" ? "og-limit__value" : "og-limit__value og-limit__value--boost"}>
              {withUnit(String(limits[key]), t.units.watts)}
            </span>
            <span className="og-limit__code">{key.toUpperCase()}</span>
            <span className="og-limit__label">{t.power.limits[key]}</span>
          </span>
        ))}
      </div>
    </Card>
  );
}

/** The CPU boost as chosen, or as it is until the user chooses. */
function BoostRow({ power, readings }: { power: Power; readings: PowerReadings | null }) {
  const t = useMessages();
  const boost = power.cpuBoost ?? readings?.cpuBoost ?? false;
  return (
    <ToggleRow
      title={t.power.cpuBoost}
      subtitle={boost ? t.power.cpuBoostOn : t.power.cpuBoostOff}
      value={boost}
      action={t.actions.toggle}
      onChange={(cpuBoost) => {
        setPower({ ...power, cpuBoost });
      }}
    />
  );
}

/** Steam's TDP slider is on but does nothing while ORIGAMI keeps the TDP; the way to switch it off. */
function SteamSliderPlate() {
  const t = useMessages();
  return (
    <>
      <Alert title={t.power.steamSlider}>{t.power.steamSliderText}</Alert>
      <Pressable
        className="og-button"
        action={t.actions.open}
        sound={UISound.Press}
        onPress={() => {
          mainWindow().MenuStore.OpenQuickAccessMenu(steamTab(QuickAccessTab.Performance));
        }}
      >
        {t.power.openPerformance}
      </Pressable>
    </>
  );
}

function BatteryLine({ battery }: { battery: BatteryTelemetry }) {
  const t = useMessages();
  const texts = batteryTexts(battery, t);
  return (
    <div className="og-battery">
      <span>
        {t.power.battery} <b>{texts.percent}</b>
        {texts.state !== null && ` · ${texts.state}`}
      </span>
      {texts.capacity !== null && (
        <span>
          {t.power.capacity} <b>{texts.capacity}</b>
        </span>
      )}
    </div>
  );
}
