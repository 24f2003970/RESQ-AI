import { Component, lazy, Suspense, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft, ArrowUpRight, Bot, Building2, CheckCircle2, CircleHelp,
  Cpu, Layers3, Presentation, Radio, RefreshCw, Route, ShieldCheck, Truck,
} from "lucide-react";
import {
  fetchAgentDashboard, fetchLatestRecommendation, fetchMissions, fetchMissionUnits,
  type AgentDashboard, type CityState, type Mission, type MissionUnitResource,
  type RescueRecommendation, type ScenarioPredictionSet, type ScenarioState, type SimulationEvent,
} from "../api/client";
import type { Layers } from "../scene/CityScene";
import { Badge } from "./ui";
import { judgeFacts } from "./judgeFacts";

const LazyCityScene = lazy(() => import("../scene/CityScene"));
const defaultLayers: Layers = {
  buildings: true, greenery: false, facilities: true, districts: false,
  units: true, flood: true, infrastructure: true, predictedRisk: false,
};
type JudgeAssignment = {
  unit_id: string;
  destination_id: string;
  route: { polyline: number[][]; distance_m: number; simulated_minutes: number };
};

export default function JudgeMode({
  city, scenario, events, status, retry, model, predictions,
}: {
  city: CityState;
  scenario: ScenarioState | null;
  events: SimulationEvent[];
  status: string;
  retry: () => void;
  model: import("../api/client").MLModelInfo | null;
  predictions: ScenarioPredictionSet | null;
}) {
  const [dashboard, setDashboard] = useState<AgentDashboard | null>(null);
  const [recommendation, setRecommendation] = useState<RescueRecommendation | null>(null);
  const [missions, setMissions] = useState<Mission[]>([]);
  const [units, setUnits] = useState<MissionUnitResource[]>([]);
  const [refreshError, setRefreshError] = useState("");
  const [lowGraphics, setLowGraphics] = useState(true);
  const [showPredicted, setShowPredicted] = useState(false);
  const [selectedBuildingId, setSelectedBuildingId] = useState<string | null>(null);
  const scenarioId = scenario?.id;
  useEffect(() => {
    if (!scenarioId) {
      setDashboard(null); setRecommendation(null); setMissions([]); setUnits([]);
      return;
    }
    let live = true;
    let latestRefresh = 0;
    const controller = new AbortController();
    const refresh = async () => {
      const refreshId = ++latestRefresh;
      const [nextDashboard, nextRecommendation, nextMissions, nextUnits] = await Promise.allSettled([
        fetchAgentDashboard(scenarioId, controller.signal), fetchLatestRecommendation(scenarioId, controller.signal),
        fetchMissions(scenarioId, controller.signal), fetchMissionUnits(scenarioId, controller.signal),
      ]);
      if (!live || controller.signal.aborted || refreshId !== latestRefresh) return;
      const errors: string[] = [];
      if (nextDashboard.status === "fulfilled") setDashboard(nextDashboard.value); else errors.push("agent status");
      if (nextRecommendation.status === "fulfilled") setRecommendation(nextRecommendation.value); else errors.push("rescue recommendation");
      if (nextMissions.status === "fulfilled") setMissions(nextMissions.value); else errors.push("mission status");
      if (nextUnits.status === "fulfilled") setUnits(nextUnits.value); else errors.push("resource availability");
      setRefreshError(errors.length ? `Could not refresh ${errors.join(", ")}. Reconnect or open the detailed workspace to retry.` : "");
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 4000);
    return () => { live = false; controller.abort(); window.clearInterval(timer); };
  }, [scenarioId]);
  const facts = useMemo(() => judgeFacts({ scenario, predictions, dashboard, recommendation, missions, model }),
    [scenario, predictions, dashboard, recommendation, missions, model]);
  const currentEvent = events.at(-1) ?? null;
  const selectedBuilding = city.buildings.find((building) => building.id === selectedBuildingId) ?? null;
  const currentPlan = facts.recommendationCurrent ? recommendation : null;
  const assignments = (currentPlan?.missions ?? []) as unknown as JudgeAssignment[];
  const comparison = currentPlan?.comparison as unknown as {
    optimized?: { destinations_covered?: number };
    baseline?: { destinations_covered?: number };
  } | undefined;
  const layerState = { ...defaultLayers, predictedRisk: showPredicted };
  const currentUnits = units.filter((unit) => unit.scenario_id === scenario?.id && unit.scenario_epoch === scenario?.epoch);
  const currentMissions = missions.filter((mission) => mission.scenario_id === scenario?.id && mission.scenario_epoch === scenario?.epoch);
  const currentRuns = facts.dashboardCurrent ? dashboard?.latest_runs.filter((run) => run.scenario_id === scenario?.id && run.scenario_epoch === scenario?.epoch && run.simulation_state_version === scenario?.state_version && run.infrastructure_revision === dashboard.infrastructure_revision) ?? [] : [];
  const availableUnits = currentUnits.filter((unit) => unit.status === "available").length;
  const committedUnits = currentUnits.filter((unit) => unit.status !== "available").length;
  const latestTraceId = facts.traceCurrent ? dashboard?.latest_trace?.event_id : undefined;

  return <main className="judge-mode" aria-label="Judge presentation mode">
    <header className="judge-header">
      <div className="judge-brand"><span className="judge-brand-mark"><Presentation size={18}/></span><div><span className="eyebrow">RESQ-AI · LIVE PRESENTATION</span><h1>Judge Mode</h1></div></div>
      <div className="judge-header-actions">
        <span className={`connection ${status}`} role="status"><i/>{status === "online" ? "Local service connected" : status === "loading" ? "Connecting to local service" : "Showing last loaded state"}</span>
        <button className="secondary-button" onClick={retry}><RefreshCw size={15}/> Refresh state</button>
        <Link className="secondary-button" to="/robustness">Robustness evidence</Link>
        <Link className="secondary-button" to="/"><ArrowLeft size={15}/> Exit Judge Mode</Link>
      </div>
    </header>
    {status === "offline" && <div className="judge-alert" role="alert"><Radio size={16}/> Local service is offline. Values below are the last loaded snapshot; current recommendations and actions are unavailable until reconnect.</div>}
    <section className="judge-stagebar" aria-label="Live demo stage">
      <div><span className="eyebrow">CURRENT EVENT</span><strong>{currentEvent ? currentEvent.event_type.replaceAll("_", " ") : scenario?.tick ? "Flood simulation state" : "Stable synthetic city"}</strong><small>{currentEvent ? `Event ${currentEvent.event_id} · state v${currentEvent.state_version}` : scenario ? `Scenario ${scenario.name} · tick ${scenario.tick} · v${scenario.state_version}` : "Waiting for the backend scenario snapshot"}</small></div>
      <div className="judge-next"><span className="eyebrow">NEXT REVIEW ACTION</span><strong>{facts.nextAction}</strong><small>Stage status follows the current backend snapshot and saved records.</small></div>
      {facts.pendingApproval && <Link className="primary-button" to="/response"><ShieldCheck size={15}/> Open commander review</Link>}
    </section>
    <ol className="judge-stage-rail" aria-label="Evidence stage status">
      {facts.stages.map((stage) => <li className={`judge-stage-${stage.status}`} key={stage.label}><span aria-hidden="true"/>{stage.label}<small>{stage.status === "recorded" ? "Recorded" : stage.status === "unavailable" ? "Unavailable" : "Pending"}</small></li>)}
    </ol>
    {refreshError && <div className="judge-alert" role="alert">{refreshError}</div>}
    <section className="judge-kpis" aria-label="Current backend metrics">
      <article><span><WavesIcon/> Simulated flood depth</span><strong>{scenario ? `${scenario.maximum_depth_m.toFixed(2)} m` : "—"}</strong><small>Peak physical simulation cell depth</small></article>
      <article><span><Building2 size={15}/> Physically exposed buildings</span><strong>{facts.exposed ?? "—"}</strong><small>Current flood simulation threshold</small></article>
      <article><span><Cpu size={15}/> Predicted future exposure</span><strong>{facts.predicted ?? "—"}</strong><small>{facts.predictionCurrent ? `${predictions?.horizon_minutes} min · local synthetic model` : "No current-version inference loaded"}</small>{facts.outOfSupportPredictions ? <small>{facts.outOfSupportPredictions} out-of-support labels excluded from planning</small> : null}</article>
      <article><span><Truck size={15}/> Rescue resources</span><strong>{units.length ? `${availableUnits} available` : "—"}</strong><small>{units.length ? `${committedUnits} committed or unavailable · backend inventory` : "Loading lifecycle records"}</small></article>
    </section>
    <div className="judge-layout">
      <section className="judge-city-panel" aria-label="Live 3D city">
        <div className="judge-city-heading"><div><span className="live-dot"/><div><h2>Riverside Digital Twin</h2><small>{scenario ? `${scenario.status} · simulated T+${Math.floor(scenario.simulated_seconds / 60)} min · version ${scenario.state_version}` : "Scenario is loading"}</small></div></div>
          <div className="judge-controls"><label><input type="checkbox" checked={lowGraphics} onChange={(event) => setLowGraphics(event.target.checked)}/> Low graphics</label><label><input type="checkbox" checked={showPredicted} disabled={!facts.predictionCurrent} onChange={(event) => setShowPredicted(event.target.checked)}/> Predicted risk layer</label></div>
        </div>
        <div className="judge-city-canvas"><SceneErrorBoundary fallback={<SceneFallback city={city} scenario={scenario}/>}><Suspense fallback={<div className="scene-loading" role="status">Loading the 3D city…</div>}><LazyCityScene city={city} scenario={scenario} selected={selectedBuilding} onSelect={setSelectedBuildingId} layers={layerState} lowGraphics={lowGraphics} predictions={facts.predictionCurrent && predictions ? { ...predictions, predictions: predictions.predictions.filter((item) => item.distribution_support_status === "within_observed_support" || item.distribution_support_status === "edge_of_observed_support") } : null} routeLines={currentPlan?.status === "proposed" ? assignments.map((item) => item.route.polyline) : []} manualClosureIds={facts.dashboardCurrent ? dashboard?.manual_closure_road_ids ?? [] : []} missions={currentMissions} missionUnits={currentUnits} selectedMissionId={null} onSelectMission={() => {}}/></Suspense></SceneErrorBoundary></div>
        <div className="judge-map-footer"><span>Simulated flood depth</span><span>{currentPlan?.status === "proposed" ? "Proposed route overlay" : currentMissions.some((mission) => ["en_route", "blocked", "arrived"].includes(mission.status)) ? "Backend mission routes" : "Select a building to inspect"}</span><span>Fictional city · local meters</span></div>
      </section>
      <aside className="judge-evidence-column" aria-label="Live system evidence">
        <section className="judge-card"><div className="judge-card-title"><h2>Agent coordination</h2><Badge tone={facts.traceCurrent && dashboard?.latest_trace?.status === "completed" ? "green" : dashboard?.latest_trace ? "amber" : ""}>{facts.traceCurrent ? dashboard?.latest_trace?.status : dashboard?.latest_trace ? "Older version" : "Waiting"}</Badge></div>
          <p>Model reliability: {model?.status === "ready" ? model.reliability_status : "model unavailable"} · calibration: {model?.calibration_status ?? "unknown"}. Current flood conditions remain simulator outputs.</p>
          <p>{facts.traceCurrent ? dashboard?.latest_trace?.summary : dashboard?.latest_trace ? "The latest trace belongs to an earlier scenario or infrastructure revision; it remains historical evidence." : "No persisted six-agent trace is available for this scenario yet."}</p>
          {currentRuns.length ? <ol className="judge-agent-list">{currentRuns.map((run) => <li key={run.run_id}><span>{run.agent_name.replaceAll("_", " ")}</span><Badge tone={run.status === "completed" ? "green" : run.status === "failed" ? "red" : "amber"}>{run.status}</Badge></li>)}</ol> : <small>No agent runs match the current scenario version; previous traces remain historical evidence.</small>}
          {latestTraceId && <Link className="judge-evidence-link" to={`/decisions?event=${encodeURIComponent(latestTraceId)}`}>View decision evidence <ArrowUpRight size={14}/></Link>}
        </section>
        <section className="judge-card"><div className="judge-card-title"><h2>Rescue recommendation</h2><Badge tone={currentPlan?.status === "approved" ? "green" : currentPlan?.status === "proposed" ? "amber" : ""}>{currentPlan?.status ?? (recommendation ? "Out of date" : "No proposal")}</Badge></div>
          {currentPlan ? (
            <>
              <p>{currentPlan.explanation}</p>
              <div className="judge-plan-metrics">
                <span>Proposed assignments<strong>{assignments.length}</strong></span>
                <span>Optimized coverage<strong>{comparison?.optimized?.destinations_covered ?? "—"}</strong></span>
                <span>Baseline coverage<strong>{comparison?.baseline?.destinations_covered ?? "—"}</strong></span>
              </div>
              {assignments.slice(0, 3).map((mission) => (
                <p className="judge-assignment" key={mission.unit_id + ":" + mission.destination_id}>
                  <Route size={13}/>
                  <span>{mission.unit_id} → {city.buildings.find((item) => item.id === mission.destination_id)?.name ?? mission.destination_id}
                    <small>{mission.route.distance_m} m · {mission.route.simulated_minutes} synthetic minutes</small>
                  </span>
                </p>
              ))}
              {currentPlan.status === "proposed" && <p className="judge-human-review"><ShieldCheck size={14}/> Commander review required. No approval is performed in Judge Mode.</p>}
            </>
          ) : <p>{recommendation ? "The saved proposal belongs to an older scenario state. Refresh it in Command Center before presenting it as current." : "No saved rescue proposal is available for the current scenario."}</p>}
          <Link className="judge-evidence-link" to="/response">Open commander controls <ArrowUpRight size={14}/></Link>
        </section>
        <section className="judge-card"><div className="judge-card-title"><h2>Mission operations</h2><Badge>{facts.activeMissions} active</Badge></div>
          <p>{facts.completedMissions} explicitly completed simulated missions · {currentMissions.filter((mission) => mission.status === "arrived").length} arrived awaiting completion confirmation.</p>
          <small>Arrival and completion are separate backend states. Neither asserts a real rescue outcome.</small>
        </section>
        <div className="judge-evidence-links"><Link to="/model"><Cpu size={15}/> Model Intelligence Lab</Link><Link to="/decisions"><Bot size={15}/> AI Decision Explorer</Link><Link to="/scenarios"><Layers3 size={15}/> Scenario Lab</Link><Link to="/demo"><CircleHelp size={15}/> Guided Demo</Link></div>
      </aside>
    </div>
    <div className="judge-honesty"><CheckCircle2 size={15}/><span>All values come from this scenario snapshot, local model inference, saved agent traces, rescue plans, and mission records. Physical flood exposure and predicted future exposure are distinct. City, population, and outcomes are synthetic.</span><Badge>{model?.status === "ready" ? `Model ${model.model_version}` : "Model unavailable"}</Badge></div>
  </main>;
}

function WavesIcon() { return <span className="judge-wave-icon" aria-hidden="true">≈</span>; }

class SceneErrorBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

function SceneFallback({ city, scenario }: { city: CityState; scenario: ScenarioState | null }) {
  const rows = [...(scenario?.impacts.buildings ?? [])]
    .filter((impact) => impact.water_reaches_building)
    .sort((a, b) => b.max_depth_m - a.max_depth_m)
    .slice(0, 8);
  return <section className="judge-scene-fallback" role="status" aria-label="City map fallback">
    <div><strong>3D view unavailable</strong><p>The backend state is still available in this evidence table.</p></div>
    <div className="judge-fallback-scroll"><table><thead><tr><th>Building</th><th>Simulated max depth</th><th>Coordinates · local meters</th></tr></thead><tbody>
      {rows.map((impact) => { const building = city.buildings.find((item) => item.id === impact.entity_id); return building ? <tr key={building.id}><td>{building.name}</td><td>{impact.max_depth_m.toFixed(2)} m</td><td>{building.position.x_m.toFixed(0)}, {building.position.y_m.toFixed(0)}</td></tr> : null; })}
      {!rows.length && <tr><td colSpan={3}>No building exposure is recorded in this scenario snapshot.</td></tr>}
    </tbody></table></div>
  </section>;
}
