// SPDX-FileCopyrightText: 2026 lexdrev
// SPDX-License-Identifier: GPL-3.0-or-later

import { useEffect } from "react";

import type { BatteryTelemetry, Limits, Power, Settings, Telemetry } from "../backend";
import { chooseOwn, profileOf, withPower, type Game } from "../gameProfiles";
import { openedProfile, runningGame } from "../games";
import { useMessages } from "../i18n";
import { formatNumber, withUnit } from "../i18n/format";
import { back, navigate } from "../navigation";
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
import { conflicts, heldPower, refreshConflicts, setGamePower, setPower, updateSettings } from "../state";
import { settings } from "../state";
import { useStore } from "../store";
import { Alert, Card, CardTitles, Header, Screen, SwitchLine } from "../ui/blocks";
import { ChoiceGroup, filledTrack, NavRow, Pressable, Slider, ToggleRow } from "../ui/controls";
import { Dial, DialFace, DialReadout, type DialStatus } from "../ui/dial";
import { useTelemetry } from "../useTelemetry";
import { OwnedBy } from "./OwnedBy";

/** Drawing less than this share of the limit, the SoC has nothing to do that needs it. */
const NO_LOAD_SHARE = 0.5;

type PowerReadings = Telemetry["power"];

/** The Power screen: the running game's strip on top, or the way to the game profiles while none runs. */
export function PowerScreen() {
  const t = useMessages();
  return <PowerView title={t.power.title} game={useStore(runningGame)} />;
}

/** A game's profile opened from the list: the Power screen as it is while that game runs. */
export function GameProfileScreen() {
  const t = useMessages();
  const game = useStore(openedProfile);
  const running = useStore(runningGame);
  if (game === null) return <PowerView title={t.power.title} game={null} />;
  return (
    <PowerView
      title={game.name}
      subtitle={running?.appId === game.appId ? undefined : t.power.profileSub}
      game={game}
    />
  );
}

interface PowerViewProps {
  title: string;
  subtitle?: string | undefined;
  game: Game | null;
}

function PowerView({ title, subtitle, game }: PowerViewProps) {
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
        <Header onBack={back} title={title} subtitle={subtitle} />
      </Screen>
    );
  }
  const power = readings.status === "ready" ? readings.value.power : null;
  const owner = owners.value.power;
  return (
    <Screen onBack={back}>
      <Header onBack={back} title={title} subtitle={subtitle} />
      {owner !== null ? (
        <>
          <DrawnDial power={power} />
          <OwnedBy title={t.power.ownedBy(owner)} text={t.power.ownedText(owner)} />
        </>
      ) : current.value.manageTdp ? (
        <OwnPower setting={current.value} power={power} game={game} />
      ) : (
        <>
          <DrawnDial power={power} />
          {/* The user switched it off, so this is their choice, not a problem. */}
          <Alert title={t.power.steamSets} problem={false}>
            {t.power.steamSetsText}
          </Alert>
          <BoostRow power={current.value.power} general={null} readings={power} onChange={setPower} />
        </>
      )}
      {power?.battery && <BatteryLine battery={power.battery} />}
    </Screen>
  );
}

interface OwnPowerProps {
  setting: Settings;
  power: PowerReadings | null;
  /** The game whose strip is on top; null for the general settings and the way to the profiles. */
  game: Game | null;
}

/**
 * ORIGAMI holds the TDP: the TDP card with its dial, then the headroom and the switches. With a game,
 * they set its own profile while it has an active one, else the general settings.
 */
function OwnPower({ setting, power, game }: OwnPowerProps) {
  const t = useMessages();
  const held = useStore(heldPower);
  const running = useStore(runningGame);
  const steamSlider = useStore(steamTdpSlider) === true;
  const profile = game === null ? undefined : profileOf(setting.gamePower, game.appId);
  const own = profile?.active === true;
  const shownPower = profile !== undefined && own ? profile.power : setting.power;
  const general = own ? setting.power : null;
  // The readings and the held limits belong to what applies now: the running game's own settings
  // while it has an active profile, else the general ones.
  const runningProfile = running === null ? undefined : profileOf(setting.gamePower, running.appId);
  const appliedGame = runningProfile?.active === true ? runningProfile.appId : null;
  const applied = appliedGame === (own ? game?.appId : null);
  const save = (next: Power) => {
    if (game !== null && own) setGamePower(withPower(setting.gamePower, game.appId, next));
    else setPower(next);
  };

  const holding = held.status === "ready" ? held.value : null;
  const heldLimits = applied ? (holding?.limits ?? null) : null;
  const highest = highestTdp(power, setting.batteryHighTdp);
  // A TDP chosen on the charger stays; on the battery the screen shows the 25 W held.
  const shown = Math.min(shownPower.tdp, highest);
  const limits = heldLimits?.spl === shown ? heldLimits : limitsFor({ ...shownPower, tdp: shown });
  const drawn = applied ? (power?.packagePowerW ?? null) : null;
  const status: DialStatus | null = steamSlider
    ? { text: t.power.steamSliderIdle, problem: true }
    : holding?.contested
      ? { text: t.power.contested, problem: true }
      : drawn !== null && drawn < shown * NO_LOAD_SHARE
        ? { text: t.power.noLoad, problem: false }
        : null;

  return (
    <>
      {game === null ? (
        <NavRow
          title={t.power.profiles}
          count={setting.gamePower.length}
          subtitle={t.power.profilesSub}
          action={t.actions.open}
          onPress={() => {
            navigate("gameProfiles");
          }}
        />
      ) : (
        <ProfileStrip setting={setting} game={game} own={own} />
      )}
      {steamSlider && <SteamSliderPlate />}
      {holding?.contested && <Alert title={t.power.contested}>{t.power.contestedText}</Alert>}
      <TdpCard
        power={shownPower}
        general={general}
        highest={highest}
        batteryHighTdp={setting.batteryHighTdp}
        drawn={drawn}
        status={status}
        onChange={save}
      />
      <HeadroomCard power={shownPower} general={general} limits={limits} onChange={save} />
      <BoostRow power={shownPower} general={general} readings={applied ? power : null} onChange={save} />
    </>
  );
}

/** The game's own settings or the general ones; the first pick of the game copies the general. */
function ProfileStrip({ setting, game, own }: { setting: Settings; game: Game; own: boolean }) {
  const t = useMessages();
  const kept = profileOf(setting.gamePower, game.appId) !== undefined;
  return (
    <>
      <ChoiceGroup
        label={t.power.profile}
        choices={[
          { value: "general", label: t.power.general },
          { value: "game", label: game.name },
        ]}
        value={own ? "game" : "general"}
        action={t.actions.select}
        onChange={(choice) => {
          setGamePower(chooseOwn(setting.gamePower, game, setting.power, choice === "game"));
        }}
      />
      <span className="og-choices__note">
        {own ? t.power.gameOnly : kept ? t.power.profileWaits : t.power.chooseGame}
      </span>
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

interface PowerCardProps {
  power: Power;
  /** The general settings while a game's own are shown, to tag what the game sets otherwise. */
  general: Power | null;
  onChange: (power: Power) => void;
}

interface TdpCardProps extends PowerCardProps {
  highest: number;
  batteryHighTdp: boolean;
  drawn: number | null;
  status: DialStatus | null;
}

/**
 * The sustained limit in one card: the dial with the title and the power drawn beside it, then the
 * scale up to its top and the presets, as the saturation. The dial shows the scale's ends; under the
 * presets the switch that unlocks the top of the scale on the battery, next to the lock it opens. It
 * is one for the general settings and every game.
 */
function TdpCard({ power, general, highest, batteryHighTdp, drawn, status, onChange }: TdpCardProps) {
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
          label={general === null ? t.power.limit : t.power.gameLimit}
          fill={{ watts: tdp, kind: "on" }}
          locked={highest < MAX_TDP ? highest : undefined}
        />
        <div className="og-tdp__side">
          <CardTitles
            title={t.power.tdp}
            badge={general !== null && general.tdp !== power.tdp ? t.power.differs(String(general.tdp)) : undefined}
            subtitle={t.power.tdpSub}
          />
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
          onChange({ ...power, tdp });
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
          if (choice !== undefined) onChange({ ...power, tdp: choice.watts });
        }}
        custom={{
          label: t.power.presets.custom,
          detail: preset === undefined ? watts(tdp) : "+",
          selected: preset === undefined,
        }}
      />
      <span className="og-card__divider" aria-hidden="true" />
      <SwitchLine
        title={t.power.batteryHigh}
        subtitle={batteryHighTdp ? t.power.batteryHighOn : t.power.batteryHighOff}
        value={batteryHighTdp}
        action={t.actions.toggle}
        onChange={(on) => void updateSettings({ batteryHighTdp: on })}
      />
    </Card>
  );
}

/** Short boosts over the TDP: the switch in the head, the three limits inside while it is on. */
function HeadroomCard({ power, general, limits, onChange }: PowerCardProps & { limits: Limits }) {
  const t = useMessages();
  return (
    <Card
      title={t.power.headroom}
      badge={general !== null && general.headroom !== power.headroom ? t.power.differs() : undefined}
      subtitle={power.headroom ? t.power.headroomOn : t.power.headroomOff}
      toggle={{
        value: power.headroom,
        action: t.actions.toggle,
        onChange: (headroom) => {
          onChange({ ...power, headroom });
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
function BoostRow({ power, general, readings, onChange }: PowerCardProps & { readings: PowerReadings | null }) {
  const t = useMessages();
  const boost = power.cpuBoost ?? readings?.cpuBoost ?? false;
  return (
    <ToggleRow
      title={t.power.cpuBoost}
      badge={general !== null && general.cpuBoost !== power.cpuBoost ? t.power.differs() : undefined}
      subtitle={boost ? t.power.cpuBoostOn : t.power.cpuBoostOff}
      value={boost}
      action={t.actions.toggle}
      onChange={(cpuBoost) => {
        onChange({ ...power, cpuBoost });
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
