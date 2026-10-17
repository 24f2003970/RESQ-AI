import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Activity, AlertTriangle, ArrowRight, CheckCircle2, FlaskConical, RefreshCw, ShieldAlert } from "lucide-react";
import type { CityState, RobustnessBaseline, RobustnessCondition, RobustnessStudy, ScenarioState } from "../api/client";
import { createRobustnessStudy, fetchRobustnessBaseline, fetchRobustnessStudies, fetchRobustnessStudy } from "../api/client";
import type { HypotheticalRoute, Layers } from "../scene/CityScene";
import { Badge, Panel } from "./ui";

const layers:Layers={buildings:true,greenery:false,facilities:true,districts:false,units:false,flood:true,infrastructure:true,predictedRisk:false};
const LazyCityScene=lazy(()=>import("../scene/CityScene"));
type ConditionResult={condition:{condition_id:string;label:string;category:string;closed_asset_ids:string[]};original_plan_feasibility:{feasible_assignments:number;total_original_assignments:number;invalidated_routes:number;assignments:{unit_id:string;destination_id:string;original_route_feasible:boolean;failure_reasons:string[]}[]};reoptimized_plan:{status:string;metrics:{reachable_priority_destinations:number;assigned_destinations:number;priority_weighted_coverage:number;coverage_denominator_priority_points:number;total_assigned_route_distance_m:number;maximum_synthetic_arrival_minutes:number;sum_synthetic_travel_minutes:number;resource_utilization:number;unserved_destinations:number};missions:{unit_id:string;destination_id:string;route:{polyline:number[][];polyline_xyz?:number[][];distance_m:number;simulated_minutes:number}}[];unreachable:unknown[]};reliability:{status:string;warnings:string[]}};
type StudyResults={conditions:ConditionResult[];critical_infrastructure:{asset_id:string;dependent_assignments:number;affected_priority_weighted_coverage:number;feasible_after_closure:boolean;alternate_route_assignments:unknown[]}[];contingencies:{contingency_id:string;trigger_condition:string;unit_id:string;destination_id:string;route:{polyline:number[][];distance_m:number;simulated_minutes:number};review_required:boolean;applied_to_live_operations:boolean}[];baseline:{missions:{unit_id:string;destination_id:string;route:{polyline:number[][]}}[]};interpretation:string;study_runtime_ms:number};

export default function RobustnessLab({city,scenario}:{city:CityState;scenario:ScenarioState|null}){
  const scenarioId=scenario?.id;
  const scenarioEpoch=scenario?.epoch;
  const stateVersion=scenario?.state_version;
  const [baseline,setBaseline]=useState<RobustnessBaseline|null>(null);
  const [study,setStudy]=useState<RobustnessStudy|null>(null);
  const [savedStudies,setSavedStudies]=useState<RobustnessStudy[]>([]);
  const [selectedCondition,setSelectedCondition]=useState("");
  const [selectedAssignment,setSelectedAssignment]=useState("");
  const [asset,setAsset]=useState("");
  const [assetKind,setAssetKind]=useState<"road_closure"|"bridge_closure">("bridge_closure");
  const [horizon,setHorizon]=useState(3);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const [refreshKey,setRefreshKey]=useState(0);
  const studyId=study?.study_id;
  useEffect(()=>{
    if(!scenarioId)return;
    const controller=new AbortController();
    Promise.all([fetchRobustnessBaseline(scenarioId,controller.signal),fetchRobustnessStudies(scenarioId,controller.signal)]).then(([value,studies])=>{setBaseline(value);setSavedStudies(studies);setError("");}).catch((reason:unknown)=>{if(!controller.signal.aborted)setError(reason instanceof Error?reason.message:"Could not load frozen baseline.");});
    return ()=>controller.abort();
  },[scenarioId,refreshKey]);
  useEffect(()=>{
    if(!scenarioId||!studyId)return;
    const controller=new AbortController();
    fetchRobustnessStudy(studyId,controller.signal).then(setStudy).catch(()=>undefined);
    return ()=>controller.abort();
  },[scenarioId,stateVersion,scenarioEpoch,studyId]);
  const assets=assetKind==="bridge_closure"?city.bridges.map(bridge=>({id:bridge.id,label:bridge.name})):city.roads.map(road=>({id:road.id,label:road.name}));
  useEffect(()=>{if(!assets.some(item=>item.id===asset))setAsset(assets[0]?.id??"");},[asset,assets]);
  const results=study?.results as StudyResults|null;
  const selected=results?.conditions.find(item=>item.condition.condition_id===selectedCondition)??results?.conditions[0];
  useEffect(()=>{if(results?.conditions.length&&!results.conditions.some(item=>item.condition.condition_id===selectedCondition))setSelectedCondition(results.conditions[0].condition.condition_id);},[results,selectedCondition]);
  const originalAssignments=results?.baseline.missions??[];
  const assignmentKey=selectedAssignment||originalAssignments[0]?.destination_id||"";
  const selectedOriginal=originalAssignments.find(item=>item.destination_id===assignmentKey);
  const fragile=results?.conditions.map(condition=>({label:condition.condition.label,result:condition.original_plan_feasibility.assignments.find(item=>item.destination_id===assignmentKey)})).filter(item=>item.result)??[];
  const overlayRoutes:HypotheticalRoute[]=useMemo(()=>selected?.reoptimized_plan.missions.map((mission,index)=>({id:`${mission.unit_id}-${mission.destination_id}`,points:mission.route.polyline_xyz??mission.route.polyline,pointsAreXYZ:Boolean(mission.route.polyline_xyz),color:index%2?"#60cdb8":"#b09aff"}))??[],[selected]);
  const hypotheticalRoadIds=selected?.condition.category==="road_closure"?selected.condition.closed_asset_ids:[];
  const hypotheticalBridgeIds=selected?.condition.category==="bridge_closure"?selected.condition.closed_asset_ids:[];
  const create=async()=>{
    if(!scenario||!baseline)return;
    setBusy(true);setError("");setMessage("");setStudy(null);
    const rainfall=Math.min(300,scenario.parameters.rainfall_mm_h+Math.max(35,scenario.parameters.rainfall_mm_h*.5));
    const conditions:RobustnessCondition[]=[
      {condition_id:"rain-escalation",label:`Rainfall increases to ${rainfall} mm/h`,category:"environment",rainfall_mm_h:rainfall},
      {condition_id:"asset-closure",label:`Hypothetical ${assetKind==="bridge_closure"?"bridge":"road"} closure: ${assets.find(item=>item.id===asset)?.label??asset}`,category:assetKind,closed_asset_ids:asset?[asset]:[]},
      {condition_id:"ambulance-unavailable",label:"One ambulance unavailable",category:"resources",unavailable_unit_type:"ambulance",unavailable_count:1},
      {condition_id:"model-unavailable",label:"Local model unavailable (fallback policy)",category:"ml_reliability",reliability_mode:"injected_unavailable"},
    ];
    try{
      const created=await createRobustnessStudy(scenario.id,baseline,conditions,Math.max(1,Math.min(12,horizon)),baseline.plans[0]?.plan_id);
      setStudy(created);setMessage(created.status==="completed"?"Study loaded from the saved identical snapshot.":"Study saved. Computing isolated conditions…");
      let current=created;
      for(let attempt=0;attempt<120&&current.status!=="completed"&&current.status!=="failed"&&current.status!=="interrupted";attempt++){
        await new Promise(resolve=>window.setTimeout(resolve,500));
        current=await fetchRobustnessStudy(created.study_id);
        setStudy(current);
      }
      if(current.status==="failed")setError(current.error??"Study failed.");
      else if(current.status==="completed")setMessage("Saved study complete. All overlays below are hypothetical.");
      else setError("Study is still running. Its saved record can be reopened from this page after refresh.");
    }catch(reason){setError(reason instanceof Error?reason.message:"Robustness study could not be created.");}
    finally{setBusy(false);}
  };
  const refreshBaseline=()=>{setStudy(null);setRefreshKey(value=>value+1);};
  return <main className="robustness-page">
    <div className="page-heading"><div><div className="breadcrumb">ANALYTICAL WORKSPACE <ArrowRight size={12}/> DECISION ROBUSTNESS</div><h1>Decision Robustness Lab<span className="heading-dot"/></h1><p>Test how a saved rescue recommendation responds to changed synthetic conditions.</p></div><Badge tone="amber">OFFLINE · ANALYTICAL ONLY</Badge></div>
    <div className="robustness-safety" role="note"><ShieldAlert size={18}/><span>Studies are hypothetical evidence. They do not change the live scenario, missions, resource reservations, road closures, agent outbox, approval, or dispatch.</span></div>
    {error&&<div className="robustness-error" role="alert"><AlertTriangle size={16}/>{error}</div>}
    {message&&<div className="robustness-message" role="status"><CheckCircle2 size={16}/>{message}</div>}
    <div className="robustness-grid">
      <Panel title="Frozen starting point" eyebrow="SNAPSHOT IDENTITY" action={<button className="icon-button" aria-label="Refresh baseline" onClick={refreshBaseline}><RefreshCw size={15}/></button>}>
        {baseline?<><div className="robustness-facts"><Fact label="Scenario" value={scenario?.name??baseline.scenario_id}/><Fact label="Tick / epoch" value={`${baseline.simulation_tick} / ${baseline.scenario_epoch}`}/><Fact label="State version" value={String(baseline.simulation_state_version)}/><Fact label="Infrastructure revision" value={String(baseline.infrastructure_revision)}/><Fact label="Available units" value={String(baseline.available_unit_ids.length)}/><Fact label="Reserved units" value={String(baseline.reserved_unit_ids.length)}/><Fact label="Model reliability" value={`${baseline.model_reliability.status} · ${baseline.model_reliability.calibration_status}`}/><Fact label="Current eligible proposal" value={baseline.plans[0]?`${baseline.plans[0].plan_id.slice(0,12)}… (${baseline.plans[0].status})`:"Generated at study start"}/></div>{savedStudies.length>0&&<div className="saved-study-list"><strong>Saved studies</strong>{savedStudies.map(item=><button key={item.study_id} className={item.stale?"stale":""} onClick={()=>{setError("");setMessage("");setStudy(item);}}><span>{item.study_id.slice(0,10)} · {item.status}</span><small>{item.stale?"Historical snapshot":`tick ${item.simulation_tick} · v${item.simulation_state_version}`} · {item.stale?item.stale_reason:"Open saved results"}</small></button>)}</div>}</>:<p className="muted">Loading the current snapshot…</p>}
      </Panel>
      <Panel title="Build a bounded study" eyebrow="FOUR DETERMINISTIC CONDITIONS">
        <div className="robustness-controls"><label>Infrastructure asset<select value={assetKind} onChange={event=>setAssetKind(event.target.value as "road_closure"|"bridge_closure")}><option value="bridge_closure">Bridge closure</option><option value="road_closure">Road closure</option></select></label><label>Asset<select value={asset} onChange={event=>setAsset(event.target.value)}>{assets.map(item=><option key={item.id} value={item.id}>{item.label}</option>)}</select></label><label>Flood horizon <span>{horizon} ticks · {horizon*5} min synthetic</span><input type="range" min={1} max={12} value={horizon} onChange={event=>setHorizon(Number(event.target.value))}/></label><button className="primary-button" disabled={!baseline||busy||!scenario||!asset} onClick={create}><FlaskConical size={16}/>{busy?"Computing isolated study…":"Run robustness study"}</button></div>
        {busy&&<div className="study-progress" role="status"><span/>Running the deterministic flood, route, and allocation engines in the background.</div>}
      </Panel>
    </div>
    {study&&<>
      <div className="study-identity"><Badge tone={study.stale?"amber":study.status==="completed"?"green":"neutral"}>{study.stale?"HISTORICAL SNAPSHOT":study.status.toUpperCase()}</Badge><span>Study {study.study_id.slice(0,12)} · SHA-256 {study.snapshot_sha256.slice(0,16)}…</span>{study.stale&&<strong>{study.stale_reason}</strong>}</div>
      {results&&<>
        <Panel title="Counterfactual result matrix" eyebrow="MEASURED FROM SAVED COMPUTATIONS" action={<span className="robustness-caption">Rows are deterministic conditions; no likelihood weighting</span>}>
          <div className="robustness-table-wrap"><table className="robustness-table"><thead><tr><th>Condition</th><th>Original routes still feasible</th><th>Invalidated</th><th>Replanned assignments</th><th>Priority coverage / eligible points</th><th>Travel sum</th><th>Reliability</th></tr></thead><tbody>{results.conditions.map(item=><tr key={item.condition.condition_id} className={selected?.condition.condition_id===item.condition.condition_id?"selected":""} onClick={()=>setSelectedCondition(item.condition.condition_id)}><th>{item.condition.label}<small>{item.condition.category}</small></th><td>{item.original_plan_feasibility.feasible_assignments}/{item.original_plan_feasibility.total_original_assignments}</td><td>{item.original_plan_feasibility.invalidated_routes}</td><td>{item.reoptimized_plan.metrics.assigned_destinations}</td><td>{item.reoptimized_plan.metrics.priority_weighted_coverage.toFixed(1)} / {item.reoptimized_plan.metrics.coverage_denominator_priority_points.toFixed(1)}</td><td>{item.reoptimized_plan.metrics.sum_synthetic_travel_minutes.toFixed(1)} min</td><td>{item.reliability.status}</td></tr>)}</tbody></table></div>
          <p className="robustness-caption">Coverage is existing priority score × occupant-capacity fraction. Denominators use each condition’s own eligible destinations; environmental changes can change those priorities.</p>
        </Panel>
        <div className="robustness-grid">
          <Panel title="Hypothetical city overlay" eyebrow="COUNTERFACTUAL ROUTES ONLY"><div className="robustness-scene-label">HYPOTHETICAL · NO MISSION ANIMATION OR LIVE STATUS CHANGE</div><div className="robustness-scene"><Suspense fallback={<div className="muted">Loading the shared city scene…</div>}><LazyCityScene city={city} scenario={scenario} selected={null} onSelect={()=>undefined} layers={layers} lowGraphics={true} predictions={null} routeLines={[]} manualClosureIds={[]} missions={[]} missionUnits={[]} selectedMissionId={null} onSelectMission={()=>undefined} hypotheticalRoutes={overlayRoutes} hypotheticalClosedRoadIds={hypotheticalRoadIds} hypotheticalClosedBridgeIds={hypotheticalBridgeIds}/></Suspense></div><div className="robustness-legend"><span><i className="route-key purple"/>Reoptimized route</span><span><i className="route-key amber"/>Hypothetical closure</span></div></Panel>
          <Panel title="Fragility inspector" eyebrow="ORIGINAL PLAN, NOT SILENTLY REASSIGNED"><label className="inspector-select">Original assignment<select value={assignmentKey} onChange={event=>setSelectedAssignment(event.target.value)}>{originalAssignments.map(item=><option key={`${item.unit_id}-${item.destination_id}`} value={item.destination_id}>{item.unit_id} → {item.destination_id}</option>)}</select></label>{selectedOriginal?<div className="fragility-list">{fragile.map(item=><article key={item.label}><strong>{item.label}</strong><Badge tone={item.result?.original_route_feasible?"green":"amber"}>{item.result?.original_route_feasible?"FEASIBLE":"INVALIDATED"}</Badge><p>{item.result?.failure_reasons.length?item.result.failure_reasons.join(" "):"Saved route remains accessible under this graph and resource condition."}</p></article>)}</div>:<p className="muted">The frozen plan has no assigned destinations to inspect.</p>}</Panel>
        </div>
        <div className="robustness-grid">
          <Panel title="Critical infrastructure dependencies" eyebrow="PERTURBATION-BASED RANKING">{results.critical_infrastructure.length?<div className="dependency-list">{results.critical_infrastructure.map(item=><article key={item.asset_id}><strong>{item.asset_id}</strong><span>{item.dependent_assignments} original assignments depend on it</span><small>{item.affected_priority_weighted_coverage.toFixed(1)} affected priority points · alternate route {item.feasible_after_closure?"observed":"not observed"}</small></article>)}</div>:<p className="muted">No original assignment traverses a ranked road or bridge, or the baseline has no assigned routes.</p>}</Panel>
          <Panel title="Contingency suggestions" eyebrow="COMMANDER REVIEW REQUIRED">{results.contingencies.length?<div className="dependency-list">{results.contingencies.slice(0,8).map(item=><article key={item.contingency_id}><strong>{item.trigger_condition}</strong><span>{item.unit_id} → {item.destination_id} · {item.route.distance_m.toFixed(0)} m</span><small>Valid under the saved hypothetical route graph. Not applied to live operations.</small></article>)}</div>:<p className="muted">No supported changed assignment was produced. The study reports infeasibility without manufacturing an alternative.</p>}</Panel>
        </div>
        <Panel title="Reliability and reproduction" eyebrow="SYNTHETIC MODEL EVIDENCE"><p>{results.interpretation}</p><div className="reproduction-row"><span>Seed {study.seed}</span><span>Algorithm {study.algorithm_version}</span><span>Horizon {study.evaluation_horizon_ticks} ticks</span><span>Runtime {results.study_runtime_ms.toFixed(1)} ms</span><span>{study.reproduction.isolation as string}</span></div>{selected?.reliability.warnings.map(warning=><p className="robustness-caption" key={warning}><AlertTriangle size={13}/>{warning}</p>)}</Panel>
      </>}
    </>}
    <div className="robustness-footnote"><Activity size={14}/> Synthetic scenario evidence only. Rescue routes are not field-safety determinations; commanders must create and validate a fresh live proposal before any approval.</div>
  </main>;
}

function Fact({label,value}:{label:string;value:string}){return <div className="robustness-fact"><span>{label}</span><strong>{value}</strong></div>;}
