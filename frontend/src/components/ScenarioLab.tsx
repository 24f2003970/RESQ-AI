import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Clock3, Pause, Play, RotateCcw, StepForward, Waves } from "lucide-react";
import {
  advanceScenario,
  createScenario,
  fetchReplay,
  resetScenario,
  transitionScenario,
  updateScenarioParameters,
  type ScenarioState,
  type SimulationEvent,
  type SimulationParameters,
  type CityState,
} from "../api/client";
import type { ScenarioEnvelope } from "../api/client";
import { Badge, Panel } from "./ui";
import ScenarioComparison from "./ScenarioComparison";
import WorkflowGuide from "./WorkflowGuide";

const presetText = {
  mild: "Mild rainfall · 8 mm/h",
  heavy: "Heavy rainfall · 90 mm/h",
  extreme: "Extreme rainfall + river overflow · 180 mm/h",
} as const;

function clock(seconds: number) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

function describe(event: SimulationEvent) {
  const value = event.payload.value;
  const names: Record<string, string> = {
    scenario_created: "Scenario created from the fixed seed",
    simulation_started: "Simulation started",
    simulation_paused: "Simulation paused",
    simulation_resumed: "Simulation resumed",
    rainfall_changed: `Rainfall set to ${Number(value).toFixed(0)} mm/h`,
    river_level_changed: `River level set to ${Number(value).toFixed(2)} m`,
    drainage_changed: `Drainage effectiveness set to ${Math.round(Number(value) * 100)}%`,
    simulation_speed_changed: `Simulation speed set to ${Number(value)}×`,
    flood_cell_updated: `${event.payload.wet_cell_count} wet grid cells · peak ${Number(event.payload.maximum_depth_m).toFixed(2)} m`,
    building_exposure_changed: "Building exposure category changed",
    road_flooded: "Road access moved to caution or flooded",
    road_reopened: "Road access reopened",
    bridge_closed: "Bridge overtopped and closed",
    bridge_reopened: "Bridge reopened",
    simulation_reset: "Returned to the seeded initial conditions",
  };
  return names[event.event_type] ?? event.event_type.replaceAll("_", " ");
}

function Metric({ label, value, suffix = "" }: { label: string; value: string | number; suffix?: string }) {
  return <div className="scenario-metric"><span>{label}</span><strong>{value}{suffix}</strong></div>;
}

export default function ScenarioLab({
  city,
  envelope,
  scenario,
  error: parentError,
  onChange,
  onRetry,
}: {
  city?: CityState;
  envelope: ScenarioEnvelope | null;
  scenario: ScenarioState | null;
  error: string;
  onChange: (next: ScenarioEnvelope) => void;
  onRetry: () => void;
}) {
  const [draft, setDraft] = useState<SimulationParameters | null>(scenario?.parameters ?? null);
  const [replay, setReplay] = useState<ScenarioEnvelope | null>(null);
  const [replayTick, setReplayTick] = useState(scenario?.tick ?? 0);
  const [localError, setLocalError] = useState("");
  const [busy, setBusy] = useState(false);
  const liveTick = scenario?.tick;
  const replayedTick = replay?.state.tick;
  const liveParams = scenario?.parameters;
  const liveVersion = scenario?.state_version;
  const liveId = scenario?.id;
  useEffect(() => {
    if (liveParams) setDraft(liveParams);
  }, [liveVersion, liveId, liveParams]);
  useEffect(() => setReplay(null), [liveId]);
  useEffect(() => setReplayTick(replayedTick ?? liveTick ?? 0), [replayedTick, liveTick]);
  const shown = replay?.state ?? scenario;
  const events = useMemo(
    () => (envelope?.events ?? []).filter((event) => event.event_type !== "simulation_tick").slice(-18).reverse(),
    [envelope?.events],
  );
  if (!scenario || !draft) {
    return <main className="scenario-page"><div className="page-heading"><div><div className="breadcrumb">OPERATIONS / SIMULATION</div><h1>Flood simulation</h1><p>Connect to the local simulation service to continue.</p></div></div><div className="scenario-error" role="alert"><AlertTriangle size={18}/><span>{parentError || "Loading the current scenario…"}</span><button className="secondary-button small" onClick={onRetry}>Retry connection</button></div></main>;
  }

  const liveState = scenario;
  const displayState = shown ?? scenario;
  const isReplay = Boolean(replay);
  const busyAction = async (action: () => Promise<ScenarioEnvelope>) => {
    if (busy) return;
    setBusy(true);
    setLocalError("");
    try {
      onChange(await action());
      setReplay(null);
    } catch (cause) {
      setLocalError(cause instanceof Error ? cause.message : "The local simulation request failed.");
    } finally {
      setBusy(false);
    }
  };
  const seek = async (tick: number) => {
    setLocalError("");
    try {
      setReplay(await fetchReplay(liveState.id, tick));
    } catch (cause) {
      setLocalError(cause instanceof Error ? cause.message : "Could not reconstruct this replay tick.");
    }
  };
  const commitDraft = () => busyAction(() => updateScenarioParameters(liveState, draft));
  const draftDirty = JSON.stringify(draft) !== JSON.stringify(liveState.parameters);
  const presets = (value: "mild" | "heavy" | "extreme") =>
    busyAction(() => createScenario(`Riverside / ${presetText[value]}`, value));

  return (
    <main className="scenario-page">
      <div className="page-heading">
        <div>
          <div className="breadcrumb">OPERATIONS <span>/</span> SIMULATION</div>
          <h1>Flood simulation<span className="heading-dot" /></h1>
          <p>Change the conditions, advance the city, and inspect the computed flood state.</p>
        </div>
        <Badge tone={isReplay ? "amber" : liveState.status === "running" ? "green" : "amber"}>
          {isReplay ? "Replay view" : liveState.status === "running" ? "Simulation running" : "Simulation paused"}
        </Badge>
      </div>
      <WorkflowGuide current={1}/>
      {(parentError || localError) && <div className="scenario-error" role="alert"><AlertTriangle size={16}/><span>{localError || parentError}</span>{parentError && <button onClick={onRetry}>Retry</button>}</div>}

      <div className="scenario-layout">
        <section className="scenario-controls">
          <Panel title="Scenario conditions" eyebrow="SYNTHETIC INPUTS" action={<Waves size={17}/>}> 
            <p className="scenario-note">Fictional city · simplified educational flood model · not a forecast.</p>
            <label className="scenario-field"><span>Deterministic preset</span>
              <select value={scenario.preset} disabled={busy || scenario.status === "running"} onChange={(event) => presets(event.target.value as "mild" | "heavy" | "extreme")}>
                {Object.entries(presetText).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label className="scenario-field"><span>Rainfall <strong>{draft.rainfall_mm_h.toFixed(0)} <small>mm/h</small></strong></span>
              <input aria-label="Rainfall intensity" type="range" min="0" max="300" step="5" value={draft.rainfall_mm_h} disabled={busy || isReplay || scenario.status === "running"} onChange={(event) => setDraft({ ...draft, rainfall_mm_h: Number(event.target.value) })}/>
              <small className="range-ends"><span>0</span><span>300 mm/h</span></small>
            </label>
            <label className="scenario-field"><span>River stage <strong>{draft.river_level_m.toFixed(2)} <small>m elevation</small></strong></span>
              <input aria-label="River level" type="range" min="-1.2" max="3.5" step="0.05" value={draft.river_level_m} disabled={busy || isReplay || scenario.status === "running"} onChange={(event) => setDraft({ ...draft, river_level_m: Number(event.target.value) })}/>
              <small className="range-ends"><span>−1.2 m</span><span>3.5 m</span></small>
            </label>
            <label className="scenario-field"><span>Drainage effectiveness <strong>{Math.round(draft.drainage_effectiveness * 100)}<small>%</small></strong></span>
              <input aria-label="Drainage effectiveness" type="range" min="0" max="1" step="0.05" value={draft.drainage_effectiveness} disabled={busy || isReplay || scenario.status === "running"} onChange={(event) => setDraft({ ...draft, drainage_effectiveness: Number(event.target.value) })}/>
              <small className="range-ends"><span>Blocked</span><span>Full capacity</span></small>
            </label>
            <label className="scenario-field"><span>Playback speed <strong>{draft.speed.toFixed(2).replace(/0+$/, "").replace(/\.$/, "")}<small>×</small></strong></span>
              <input aria-label="Simulation speed" type="range" min="0.25" max="4" step="0.25" value={draft.speed} disabled={busy || isReplay || scenario.status === "running"} onChange={(event) => setDraft({ ...draft, speed: Number(event.target.value) })}/>
              <small className="range-ends"><span>¼×</span><span>4×</span></small>
            </label>
            <button className="secondary-button apply-conditions" disabled={busy || isReplay || scenario.status === "running" || !draftDirty} onClick={commitDraft}>Apply conditions</button>
            <div className="scenario-actions">
              {scenario.status === "running"
                ? <button className="secondary-button" disabled={busy || isReplay} onClick={() => busyAction(() => transitionScenario(liveState, "pause"))}><Pause size={15}/> Pause</button>
                : <button className="primary-button" disabled={busy || isReplay} onClick={() => busyAction(() => transitionScenario(liveState, liveState.tick ? "resume" : "start"))}><Play size={15}/> {liveState.tick ? "Resume" : "Start simulation"}</button>}
              <button className="secondary-button" disabled={busy || isReplay || scenario.status === "running"} onClick={() => busyAction(() => advanceScenario(liveState, 1, true))}><StepForward size={15}/> Step +5 min</button>
              <button className="icon-button" title="Reset to the seeded initial conditions" aria-label="Reset scenario" disabled={busy || isReplay || scenario.status === "running"} onClick={() => busyAction(() => resetScenario(liveState))}><RotateCcw size={15}/></button>
            </div>
          </Panel>

          <Panel title="Water depth" eyebrow="SIMULATED SURFACE" action={<Waves size={17}/> }>
            <div className="depth-legend">
              <div><i className="depth-shallow"/><span>Shallow</span><strong>0.05–0.30 m</strong></div>
              <div><i className="depth-moderate"/><span>Moderate</span><strong>0.30–1.00 m</strong></div>
              <div><i className="depth-deep"/><span>Deep</span><strong>1.00–2.00 m</strong></div>
              <div><i className="depth-extreme"/><span>Very deep</span><strong>2.00 m+</strong></div>
            </div>
            <p className="scenario-note">Road caution ≥0.10 m · road flooded ≥0.30 m · building exposure ≥0.05 m · bridge closure uses simulated water surface vs deck.</p>
          </Panel>
        </section>

        <section className="scenario-results">
          <Panel title={displayState.name} eyebrow={isReplay ? "RECONSTRUCTED STATE" : "BACKEND STATE"} action={<Badge>{isReplay ? "READ ONLY" : `V${displayState.state_version}`}</Badge>}>
            <div className="scenario-clock"><Clock3 size={17}/><strong>{clock(displayState.simulated_seconds)}</strong><span>simulated · tick {displayState.tick} · {liveState.parameters.rainfall_mm_h.toFixed(0)} mm/h current rainfall</span></div>
            <div className="scenario-metrics">
              <Metric label="Peak depth" value={displayState.maximum_depth_m.toFixed(2)} suffix=" m"/>
              <Metric label="Buildings reached" value={displayState.affected_buildings}/>
              <Metric label="Roads caution / flooded" value={displayState.exposed_roads}/>
              <Metric label="Bridges closed" value={displayState.closed_bridges}/>
            </div>
            <div className="scenario-balance">
              <span>Water volume accounting</span>
              <strong>{displayState.mass_balance.stored_m3.toLocaleString(undefined, { maximumFractionDigits: 0 })} m³ stored</strong>
              <small>Mass-balance error {displayState.mass_balance.balance_error_m3.toExponential(2)} m³</small>
            </div>
            {isReplay && <button className="text-button" onClick={() => setReplay(null)}>Return to live state</button>}
          </Panel>

          <Panel title="Timeline & replay" eyebrow="PERSISTED EVENTS" action={<Badge>{events.length} events</Badge>}>
            <label className="replay-seek"><span>Seek simulation tick</span><strong>{replay?.state.tick ?? liveState.tick} / {liveState.tick}</strong>
              <input aria-label="Replay simulation tick" type="range" min="0" max={Math.max(1, liveState.tick)} value={replayTick} disabled={liveState.tick === 0 || busy} onChange={(event) => setReplayTick(Number(event.target.value))} onPointerUp={() => void seek(replayTick)} onKeyUp={() => void seek(replayTick)}/>
            </label>
            <ol className="event-list">
              {events.map((event) => <li key={event.event_id}>
                <button className="event-item" disabled={event.tick > liveState.tick || busy} onClick={() => void seek(event.tick)}>
                  <span className="event-marker"/>
                  <span className="event-copy"><strong>{describe(event)}</strong><small>{clock(event.simulated_seconds)} · tick {event.tick} · v{event.state_version}</small>{event.entity_ids.length > 0 && <small>{event.entity_ids.slice(0, 3).join(", ")}{event.entity_ids.length > 3 ? ` +${event.entity_ids.length - 3}` : ""}</small>}</span>
                </button>
              </li>)}
              {!events.length && <li className="scenario-note">Scenario events will appear here as state changes occur.</li>}
            </ol>
            <p className="scenario-note">Replay reconstructs saved steps from the fixed seed and event parameters. Branching from past ticks is disabled.</p>
          </Panel>
        </section>
      </div>
      <details className="workspace-evidence"><summary>Compare scenarios · advanced</summary>{city ? <ScenarioComparison scenario={scenario} city={city}/> : <p className="scenario-note">Connect to the local city service to load road options for reproducible A/B experiments.</p>}</details>
      <p className="scenario-disclaimer"><span className="live-dot"/> RESQ-AI FLOOD SIMULATION · EDUCATIONAL FICTIONAL SCENARIO · NOT AN OPERATIONAL WARNING SYSTEM</p>
    </main>
  );
}
