import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useState,
  type ComponentProps,
} from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  ArrowDownToLine,
  ArrowRight,
  Bot,
  Building2,
  ChevronRight,
  Clock3,
  Hospital,
  Layers3,
  RefreshCw,
  ServerOff,
  Settings2,
  ShieldCheck,
  Trees,
  Truck,
  Waves,
  X,
} from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import type { Layers } from "../scene/CityScene";
import { fetchAgentDashboard, fetchBuilding, type Building, type CityState, type ScenarioState, type SimulationEvent } from "../api/client";
import type { MLModelInfo, ScenarioPredictionSet } from "../api/client";
import { Badge, Help, Panel, Row } from "./ui";
import Inspector from "./Inspector";
import RescuePlanning from "./RescuePlanning";
import { AgentCommandPanel } from "./AgentExplorer";
import type { Plan } from "./RescuePlanning";
import MissionOperations from "./MissionOperations";
import RobustnessSummary from "./RobustnessSummary";
import type { Mission, MissionClock, MissionUnitResource } from "../api/client";
import WorkflowGuide from "./WorkflowGuide";
import SceneSelection from "./SceneSelection";

const LazyCityScene = lazy(() => import("../scene/CityScene"));
function CityScene(props: ComponentProps<typeof LazyCityScene>) {
  return (
    <Suspense
      fallback={
        <div className="city-scene scene-loading">Preparing city geometry…</div>
      }
    >
      <LazyCityScene {...props} />
    </Suspense>
  );
}

export default function CityWorkspace({
  city,
  scenario,
  events,
  studio,
  response = false,
  status,
  retry,
  model,
  predictions,
}: {
  city: CityState;
  scenario: ScenarioState | null;
  events: SimulationEvent[];
  studio: boolean;
  response?: boolean;
  status: string;
  retry: () => void;
  model: MLModelInfo | null;
  predictions: ScenarioPredictionSet | null;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Building | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [rescuePlan, setRescuePlan] = useState<Plan|null>(null);
  const [manualClosureIds,setManualClosureIds]=useState<string[]>([]);
  const [missionSnapshot,setMissionSnapshot]=useState<{scenarioId:string|null;scenarioEpoch:number|null;missions:Mission[];units:MissionUnitResource[];clock:MissionClock|null}>({scenarioId:null,scenarioEpoch:null,missions:[],units:[],clock:null});
  const [selectedMissionId,setSelectedMissionId]=useState<string|null>(null);
  const acceptMissions=useCallback((snapshot:{missions:Mission[];units:MissionUnitResource[];clock:MissionClock|null})=>{
    setMissionSnapshot(snapshot as typeof missionSnapshot);
  },[]);
  const selectMission=useCallback((missionId:string|null)=>setSelectedMissionId(missionId),[]);
  const [searchParams]=useSearchParams();
  const reviewing = response || searchParams.has("review");
  const missionView = reviewing && searchParams.get("view") === "missions";
  const scenarioId=scenario?.id;
  const missionSnapshotIsCurrent=Boolean(scenario&&missionSnapshot.scenarioId===scenario.id&&missionSnapshot.scenarioEpoch===scenario.epoch);
  const missionRecords=missionSnapshotIsCurrent?missionSnapshot.missions:[];
  const missionUnits=missionSnapshotIsCurrent?missionSnapshot.units:[];
  const visibleSelectedMissionId=missionSnapshotIsCurrent?selectedMissionId:null;
  const currentPredictions = scenario && predictions?.scenario_id === scenario.id && predictions.scenario_epoch === scenario.epoch && predictions.scenario_state_version === scenario.state_version && predictions.scenario_tick === scenario.tick && predictions.model_version === model?.model_version ? predictions : null;
  const supportedPredictions = currentPredictions ? { ...currentPredictions, predictions: currentPredictions.predictions.filter((item) => item.distribution_support_status === "within_observed_support" || item.distribution_support_status === "edge_of_observed_support") } : null;
  const [layerOpen, setLayerOpen] = useState(false);
  const [lowGraphics, setLowGraphics] = useState(() => {
    try { return localStorage.getItem("resq-graphics") === "low"; } catch { return false; }
  });
  function toggleGraphics() {
    const next = !lowGraphics;
    setLowGraphics(next);
    try { localStorage.setItem("resq-graphics", next ? "low" : "standard"); } catch { /* The scene remains usable when browser storage is unavailable. */ }
  }
  const [layers, setLayers] = useState<Layers>({
    buildings: true,
    greenery: true,
    facilities: true,
    districts: false,
    units: true,
    flood: true,
    infrastructure: true,
    predictedRisk: false,
  });
  useEffect(() => {
    setSelected(null);
    setDetailError("");
    if (!selectedId) {
      setDetailLoading(false);
      return;
    }
    const controller = new AbortController();
    setDetailLoading(true);
    fetchBuilding(selectedId, city, controller.signal)
      .then((building) => {
        if (!controller.signal.aborted) {
          setSelected(building);
          setDetailLoading(false);
        }
      })
      .catch((e: unknown) => {
        if (!controller.signal.aborted) {
          setDetailError(
            e instanceof Error ? e.message : "Cannot load building details.",
          );
          setDetailLoading(false);
        }
      });
    return () => controller.abort();
  }, [selectedId, city]);
  useEffect(()=>{
    const destination=searchParams.get("destination");
    if(destination&&city.buildings.some(building=>building.id===destination))setSelectedId(destination);
  },[searchParams,city.buildings]);
  useEffect(()=>{
    if(!scenarioId)return;let live=true;let sequence=0;
    const refresh=()=>{const requestId=++sequence;fetchAgentDashboard(scenarioId).then(status=>{if(live&&requestId===sequence)setManualClosureIds(status.manual_closure_road_ids??[])}).catch(()=>{});};
    refresh();const timer=window.setInterval(refresh,3000);return()=>{live=false;window.clearInterval(timer)};
  },[scenarioId]);
  function downloadSnapshot() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(city, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `${city.city.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <main className={`workspace ${studio ? "studio" : ""} ${reviewing ? "response-workspace" : "overview-workspace"}`}>
      <div className="page-heading">
        <div>
          <div className="breadcrumb">
            WORKSPACE <ChevronRight size={12} />
            {studio ? "DIGITAL TWIN" : reviewing ? "RESCUE OPERATIONS" : "OVERVIEW"}
          </div>
          <h1>
            {studio ? "Digital Twin Studio" : reviewing ? "Rescue operations" : "Situation overview"}
            <span className="heading-dot" />
          </h1>
          <p>
            {studio
              ? "Explore the city. Inspect the details."
              : reviewing ? "Review a plan, approve it, then dispatch and track your units." : "See the flood situation, then choose your next step below."}
          </p>
        </div>
        <div className="workspace-actions">
          <Link className="primary-button" to={reviewing ? "/scenarios" : "/response"}>{reviewing ? "Adjust flood simulation" : "Open rescue operations"} <ArrowRight size={14}/></Link>
          <details className="workspace-more"><summary className="secondary-button">More options</summary><div>
          <Link className="secondary-button" to="/robustness">Test plan robustness <ArrowRight size={14}/></Link>
          <button className="secondary-button" onClick={downloadSnapshot}>
            <ArrowDownToLine size={15} /> Export snapshot
          </button>
          </div></details>
        </div>
      </div>
      {!studio && <WorkflowGuide current={reviewing ? missionView ? 3 : 2 : 0}/>}
      {reviewing && <nav className="response-switch" aria-label="Rescue operation steps">
        <Link to="/response" aria-current={!missionView ? "page" : undefined}>1. Plan &amp; approve</Link>
        <Link to="/response?view=missions" aria-current={missionView ? "page" : undefined}>2. Dispatch &amp; track</Link>
        <p>{missionView ? "Dispatch is a separate action after approval. Arrival, completion and return-to-service each need your confirmation." : "A recommendation reserves no units until you explicitly approve it. Then open Dispatch & track."}</p>
      </nav>}
      {status === "offline" && (
        <div className="connection-banner" role="alert">
          <ServerOff size={17} />
          <span>Backend offline. Showing the last loaded snapshot.</span>
          <button onClick={retry}>
            Reconnect <RefreshCw size={13} />
          </button>
        </div>
      )}
      {!studio && !reviewing && (
        <div className="stats-grid">
          {[
            {
              label: "Rainfall intensity",
              value: scenario?.parameters.rainfall_mm_h.toFixed(0) ?? "—",
              unit: "mm/h",
              icon: Waves,
              note: scenario?.preset ? `${scenario.preset} synthetic scenario` : "Loading simulation state",
            },
            {
              label: "Simulated elapsed time",
              value: scenario ? `${String(Math.floor(scenario.simulated_seconds / 3600)).padStart(2, "0")}:${String(Math.floor((scenario.simulated_seconds % 3600) / 60)).padStart(2, "0")}` : "00:00",
              unit: "",
              icon: Clock3,
              note: scenario?.status === "running" ? "Advancing in Scenario Lab" : "Simulation paused",
            },
            {
              label: "Maximum flood depth",
              value: scenario?.maximum_depth_m.toFixed(2) ?? "0.00",
              unit: "m",
              icon: Waves,
              note: "Peak backend-computed cell depth",
            },
            {
              label: "Physically exposed buildings",
              value: scenario?.affected_buildings ?? 0,
              unit: "",
              icon: Building2,
              note: "Footprint samples at ≥0.05 m",
            },
          ].map((s) => (
            <div className="stat-card" key={s.label}>
              <div>
                <span>{s.label}</span>
                <s.icon size={17} />
              </div>
              <strong>{s.value}<small className="stat-unit">{s.unit}</small></strong>
              <small>
                <i />
                {s.note}
              </small>
            </div>
          ))}
        </div>
      )}
      <div className="main-grid">
        <div className="main-column">
          <section className="viewport-panel">
            <div className="viewport-heading">
              <div>
                <span className="live-dot" />
                <h2>Riverside Digital Twin</h2>
                <Badge>3D CITY</Badge>
              </div>
              <div>
                <button
                  className={`secondary-button small ${lowGraphics ? "active" : ""}`}
                  aria-pressed={lowGraphics}
                  onClick={toggleGraphics}
                  title="Cap pixel ratio and disable shadows for weaker GPUs"
                >
                  <Settings2 size={14} />
                  {lowGraphics ? "Low graphics: On" : "Low graphics: Off"}
                </button>
                <button
                  className={`secondary-button small ${layerOpen ? "active" : ""}`}
                  aria-expanded={layerOpen}
                  onClick={() => setLayerOpen(!layerOpen)}
                >
                  <Layers3 size={14} /> Layers
                </button>
              </div>
            </div>
            <p className="graphics-mode-note" role="status">{lowGraphics ? "Lighter rendering: fewer details and no shadows. Flood values, routes and missions stay the same." : "Standard rendering. Turn on low graphics if the city feels slow."}</p>
            <div className="viewport-wrap">
              <CityScene
                city={city}
                scenario={scenario}
                selected={selected}
                onSelect={setSelectedId}
                layers={layers}
                lowGraphics={lowGraphics}
                predictions={supportedPredictions}
                routeLines={rescuePlan?.status === "proposed" && rescuePlan.scenario_version === scenario?.state_version ? rescuePlan.missions.map(m=>m.route.polyline) : []}
                manualClosureIds={manualClosureIds}
                missions={missionRecords}
                missionUnits={missionUnits}
                selectedMissionId={visibleSelectedMissionId}
                onSelectMission={selectMission}
              />
              <AnimatePresence>
                {layerOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="layer-menu"
                  >
                    <div>
                      <strong>Map layers</strong>
                      <button
                        aria-label="Close layers"
                        onClick={() => setLayerOpen(false)}
                      >
                        <X size={14} />
                      </button>
                    </div>
                    {(Object.keys(layers) as (keyof Layers)[]).map((key) => (
                      <label key={key}>
                        <span>{{buildings:"Buildings", greenery:"Greenery", facilities:"Emergency facilities", districts:"Districts", units:"Rescue units", flood:"Current flood depth", infrastructure:"Roads and bridges", predictedRisk:"Future ML exposure"}[key]}</span>
                        <input
                          type="checkbox"
                          checked={layers[key]}
                          onChange={() =>
                            setLayers((l) => ({ ...l, [key]: !l[key] }))
                          }
                        />
                      </label>
                    ))}
                    <p>Current flood depth comes from the physical simulation. Predicted exposure is a separate ML layer for the next 30 minutes.</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
            <SceneSelection building={selected} scenario={scenario} predictions={supportedPredictions} mission={missionRecords.find((mission) => mission.mission_id === visibleSelectedMissionId) ?? null}/>
            <div className="viewport-footer">
              <span>
                <i className="legend-block" />
                Buildings
              </span>
              <span>
                <i className="legend-water" />
                Canal
              </span>
              <span>
                <i className="legend-facility" />
                Facilities
              </span>
              <span className="mini-depth-legend" aria-label="Flood depth legend">
                <i className="depth-shallow" title="Shallow: 0.05–0.30 m"/>
                <i className="depth-moderate" title="Moderate: 0.30–1.00 m"/>
                <i className="depth-deep" title="Deep: 1.00–2.00 m"/>
                <i className="depth-extreme" title="Very deep: over 2.00 m"/>
                <span>Water depth</span>
              </span>
              {layers.predictedRisk && <span><i className="legend-predicted"/> Predicted future exposure</span>}
              {rescuePlan?.status === "proposed" && rescuePlan.scenario_version === scenario?.state_version && <span><i className="legend-planned-route"/> Proposed rescue route</span>}
              {missionRecords.some((mission) => ["en_route", "blocked", "arrived"].includes(mission.status)) && <span><i className="legend-current-route"/> Backend mission route</span>}
              <span className="viewport-state">
                {scenario ? `${scenario.status.toUpperCase()} · T+${String(Math.floor(scenario.simulated_seconds / 3600)).padStart(2, "0")}:${String(Math.floor((scenario.simulated_seconds % 3600) / 60)).padStart(2, "0")} · V${scenario.state_version}` : "LOADING SCENARIO"}
              </span>
            </div>
            <details className="scene-legend-guide"><summary>Understand the map colours &amp; routes</summary><div>
              <p><strong>Current water · physical simulation</strong><span>Depth at the current tick. Blue water is separate from future model estimates.</span></p>
              <ul className="readable-depth-legend"><li><i className="depth-shallow"/>0.05–0.30 m · shallow</li><li><i className="depth-moderate"/>0.30–1.00 m · moderate</li><li><i className="depth-deep"/>1.00–2.00 m · deep</li><li><i className="depth-extreme"/>Over 2.00 m · very deep</li></ul>
              <p><strong>Future ML exposure · estimate</strong><span>Enable Future ML exposure in Layers to see supported estimates for the next 30 simulated minutes. This does not change the water. {currentPredictions ? "Current prediction response is available." : "A current prediction is unavailable or still loading."}</span></p>
              <p><strong>Rescue routes · saved road geometry</strong><span>Bright cyan: proposed route. Muted green: ready mission. Green: active route. Red: blocked mission. Selected routes are brighter. Dashed lines in analytical views are hypothetical.</span></p>
            </div></details>
          </section>
          <div className="support-grid" hidden={reviewing}>
            <Panel
              title="Infrastructure"
              eyebrow="CITY NETWORK"
              action={<Waves size={17} />}
            >
              <div className="infrastructure-count">
                <strong>
                  {city.roads.length}
                  <small>roads</small>
                </strong>
                <span>+</span>
                <strong>
                  {city.bridges.length}
                  <small>bridges</small>
                </strong>
                  <Badge tone={scenario?.exposed_roads ? "amber" : undefined}>{scenario?.exposed_roads ?? 0} exposed</Badge>
              </div>
              <div className="infrastructure-track">
                {city.roads.map((r) => (
                  <span key={r.id} className={`road-${scenario?.impacts.roads.find((road) => road.entity_id === r.id)?.status ?? "open"}`} title={`${r.name} · ${scenario?.impacts.roads.find((road) => road.entity_id === r.id)?.status ?? r.status}`} />
                ))}
              </div>
              <p className="muted">
                Water depth determines caution and flooded status. {scenario?.closed_bridges ?? 0} bridges currently closed by the modeled river stage.
              </p>
            </Panel>
            <Panel
              title="Response readiness"
              eyebrow="LOCAL INVENTORY"
              action={<Truck size={17} />}
            >
              {(["ambulance", "boat", "rescue_team"] as const).map((type) => (
                <Row
                  key={type}
                  title={
                    {
                      ambulance: "Ambulances",
                      boat: "Rescue boats",
                      rescue_team: "Rescue teams",
                    }[type]
                  }
                  subtitle={missionUnits.length ? `${missionUnits.filter((unit) => unit.status === "available" && city.rescue_units.some((resource) => resource.id === unit.unit_id && resource.type === type)).length} available · ${missionUnits.filter((unit) => unit.status !== "available" && city.rescue_units.some((resource) => resource.id === unit.unit_id && resource.type === type)).length} committed` : "Loading current resource state"}
                  value={
                    <span className="count-pill">
                      {missionUnits.length
                        ? missionUnits.filter((unit) => unit.status === "available" && city.rescue_units.some((resource) => resource.id === unit.unit_id && resource.type === type)).length
                        : "—"}
                    </span>
                  }
                />
              ))}
            </Panel>
          </div>
          <div hidden={reviewing}><Panel
            title="Workspace activity"
            eyebrow="STATE RECORD"
            action={<Badge>Version {scenario?.state_version ?? city.scenario.state_version}</Badge>}
          >
            <div className="command-events">
              {events.filter((event) => event.event_type !== "simulation_tick").slice(-4).reverse().map((event) => (
                <div className="timeline-entry" key={event.event_id}>
                  <span className="timeline-point" />
                  <span className="mono">T+{String(Math.floor(event.simulated_seconds / 3600)).padStart(2, "0")}:{String(Math.floor((event.simulated_seconds % 3600) / 60)).padStart(2, "0")}</span>
                  <div><strong>{event.event_type.replaceAll("_", " ")}</strong><p>{event.entity_ids.length ? `${event.entity_ids.slice(0, 2).join(", ")}${event.entity_ids.length > 2 ? ` +${event.entity_ids.length - 2}` : ""}` : `Simulation tick ${event.tick} · state version ${event.state_version}`}</p></div>
                  <Badge>v{event.state_version}</Badge>
                </div>
              ))}
              {!events.length && <p className="muted">No scenario events are available yet.</p>}
            </div>
            <p className="activity-note">{city.buildings.length} buildings · {scenario?.affected_buildings ?? 0} reached · {scenario?.exposed_roads ?? 0} roads at caution or flooded. These rules describe physical exposure and accessibility, not rescue priority.</p>
            <p className="activity-note">
              Local SQLite stores scenario state, checkpoints, and deterministic event history.
            </p>
          </Panel></div>
        </div>
        <aside className="right-column">
          <div hidden={!missionView}><MissionOperations scenario={scenario} city={city} onSnapshot={acceptMissions} onSelectMission={selectMission} selectedMissionId={visibleSelectedMissionId}/></div>
          <div hidden={!reviewing || missionView}><RescuePlanning city={city} scenario={scenario} onPlan={setRescuePlan}/>
            {rescuePlan?.status === "approved" && rescuePlan.scenario_id === scenario?.id && rescuePlan.scenario_epoch === scenario?.epoch && <div className="approved-next-step"><strong>Plan approved. Dispatch is next.</strong><p>Review the current mission list and dispatch ready units explicitly.</p><Link className="primary-button" to="/response?view=missions">Open mission controls <ArrowRight size={14}/></Link></div>}
          </div>
          {!reviewing && !studio && <Panel title="Ready to respond?" eyebrow="NEXT STEP"><p className="muted">Review the proposed assignments before committing resources. Mission controls are in Rescue operations.</p><Link className="primary-button" to="/response">Review rescue plan <ArrowRight size={14}/></Link></Panel>}
          <details className="workspace-evidence"><summary>Decision evidence &amp; advanced analysis</summary><div className="evidence-panels"><RobustnessSummary scenario={scenario}/><AgentCommandPanel scenarioId={scenario?.id??null}/><Link className="secondary-button" to="/decisions">Explore agent decisions <ArrowRight size={14}/></Link></div></details>
          <div id="building-details"><Inspector
            selected={selected}
            city={city}
            loading={detailLoading}
            error={detailError}
            close={() => setSelectedId(null)}
            choose={setSelectedId}
                predictions={currentPredictions}
            scenario={scenario}
          /></div>
          <div hidden={reviewing}><Panel
            title="Critical facilities"
            eyebrow="ESSENTIAL SERVICES"
            action={<Hospital size={17} />}
          >
            {city.hospitals.map((h) => (
              <Row
                key={h.id}
                title={h.name}
                subtitle={`${h.capacity} beds · seeded capacity`}
                value={
                  <span className="facility-icon">
                    <Hospital size={15} />
                  </span>
                }
                onClick={() => setSelectedId(h.building_id)}
              />
            ))}
            {city.shelters.map((s) => (
              <Row
                key={s.id}
                title={s.name}
                subtitle={`${s.capacity} places · ${s.occupancy} occupied`}
                value={
                  <span className="facility-icon">
                    <ShieldCheck size={15} />
                  </span>
                }
                onClick={() => setSelectedId(s.building_id)}
              />
            ))}
          </Panel>
          <section className="ai-card">
            <span className="ai-icon">
              <Bot size={19} />
            </span>
            <div>
              <h2>Flood risk intelligence</h2>
              <p>{currentPredictions ? `${supportedPredictions?.predictions.filter((p) => p.predicted_future_exposed).length ?? 0} supported model labels estimate future exposure within ${currentPredictions.horizon_minutes} simulated minutes. Current exposure remains based on simulated water depth.` : "Current model prediction is unavailable, stale, or still loading; simulated physical exposure remains available."}</p>
              {supportedPredictions?.predictions.filter((p) => p.predicted_future_exposed).slice(0, 3).map((prediction) => {
                const building = city.buildings.find((item) => item.id === prediction.building_id);
                return building ? <button key={building.id} className="predicted-building-link" onClick={() => setSelectedId(building.id)}>{building.name} <span>predicted exposed</span></button> : null;
              })}
              <Badge tone={model?.status === "ready" && model.reliability_status === "available" ? "green" : "amber"}>{model?.status !== "ready" ? model?.unavailable_reason ?? "Model unavailable" : `Local model · ${model.model_version} · ${model.reliability_status}`}</Badge>
              {model?.reliability_warnings.map((warning) => <small className="reliability-warning" key={warning}>{warning}</small>)}
              <Link className="risk-lab-link" to="/model">Open Model Intelligence Lab <ArrowRight size={14}/></Link>
            </div>
          </section>
          <div className="provenance">
            <Trees size={15} />
            <p>
              Fictional city, real application state.
              <span>
                Generator {city.city.generator_version} · Local meters
              </span>
            </p>
            <Help text="City geometry, occupants, facilities and resource counts are generated deterministically by the Python backend. They do not represent a real city." />
          </div></div>
        </aside>
      </div>
    </main>
  );
}
