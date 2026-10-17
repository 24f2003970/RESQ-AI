import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
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
  const liveIdentity=`${scenarioId??"<none>"}:${scenarioEpoch??-1}`;
  const liveSnapshotIdentity=`${liveIdentity}:${stateVersion??-1}`;
  const liveIdentityRef=useRef(liveIdentity);
  const liveSnapshotIdentityRef=useRef(liveSnapshotIdentity);
  liveIdentityRef.current=liveIdentity;
  liveSnapshotIdentityRef.current=liveSnapshotIdentity;
  const [baseline,setBaseline]=useState<RobustnessBaseline|null>(null);
  const [study,setStudy]=useState<RobustnessStudy|null>(null);
  const [studyViewIdentity,setStudyViewIdentity]=useState(liveIdentity);
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
    setBaseline(null);setStudy(null);setSavedStudies([]);setSelectedCondition("");setSelectedAssignment("");
    setBusy(false);setError("");setMessage("");
  },[scenarioId,scenarioEpoch]);
  useEffect(()=>{
    if(!scenarioId)return;
    const controller=new AbortController();
    const requestIdentity=liveSnapshotIdentity;
    Promise.all([fetchRobustnessBaseline(scenarioId,controller.signal),fetchRobustnessStudies(scenarioId,controller.signal)]).then(([value,studies])=>{
      if(controller.signal.aborted||liveSnapshotIdentityRef.current!==requestIdentity)return;
      if(value.scenario_id!==scenarioId||value.scenario_epoch!==scenarioEpoch||value.simulation_state_version!==stateVersion)return;
      setBaseline(value);setSavedStudies(studies.filter(item=>item.scenario_id===scenarioId));setError("");
    }).catch((reason:unknown)=>{if(!controller.signal.aborted&&liveSnapshotIdentityRef.current===requestIdentity)setError(reason instanceof Error?reason.message:"Could not load frozen baseline.");});
    return ()=>controller.abort();
  },[scenarioId,scenarioEpoch,stateVersion,refreshKey,liveSnapshotIdentity]);
  useEffect(()=>{
    if(!scenarioId||!studyId)return;
    const controller=new AbortController();
    const requestIdentity=liveIdentity;
    fetchRobustnessStudy(studyId,controller.signal).then(value=>{
      if(controller.signal.aborted||liveIdentityRef.current!==requestIdentity)return;
      if(value.study_id!==studyId||value.scenario_id!==scenarioId)return;
      setStudy(value);
    }).catch((reason:unknown)=>{if(!controller.signal.aborted&&liveIdentityRef.current===requestIdentity)setError(reason instanceof Error?reason.message:"Could not refresh the selected saved study.");});
    return ()=>controller.abort();
  },[scenarioId,scenarioEpoch,stateVersion,studyId,liveIdentity]);
  const visibleBaseline=baseline&&baseline.scenario_id===scenarioId&&baseline.scenario_epoch===scenarioEpoch&&baseline.simulation_state_version===stateVersion?baseline:null;
  const assets=assetKind==="bridge_closure"?city.bridges.map(bridge=>({id:bridge.id,label:bridge.name})):city.roads.map(road=>({id:road.id,label:road.name}));
  useEffect(()=>{if(!assets.some(item=>item.id===asset))setAsset(assets[0]?.id??"");},[asset,assets]);
  const studyBelongsToScenario=Boolean(study&&study.scenario_id===scenarioId);
  const studyStateMismatch=Boolean(study&&scenario&&study.simulation_state_version!==scenario.state_version);
  const studyEpochMismatch=Boolean(study&&scenario&&study.scenario_epoch!==scenario.epoch);
  const studyInfrastructureMismatch=Boolean(study&&baseline&&study.infrastructure_revision!==baseline.infrastructure_revision);
  const historicalReason=study?.stale_reason??(studyEpochMismatch?"This study belongs to an earlier scenario replay epoch.":studyStateMismatch?"The live simulation state advanced after this study was frozen.":studyInfrastructureMismatch?"Infrastructure changed after this study was frozen.":null);
  const displayStudy=studyViewIdentity===liveIdentity&&studyBelongsToScenario&&study?{...study,stale:study.stale||studyEpochMismatch||studyStateMismatch||studyInfrastructureMismatch,stale_reason:historicalReason}:null;
  const currentStudyEvidence=Boolean(displayStudy&&!displayStudy.stale&&displayStudy.scenario_epoch===scenarioEpoch&&displayStudy.simulation_state_version===stateVersion&&displayStudy.infrastructure_revision===baseline?.infrastructure_revision);
  const results=displayStudy?.results as StudyResults|null;
  const selected=results?.conditions.find(item=>item.condition.condition_id===selectedCondition)??results?.conditions[0];
  useEffect(()=>{if(results?.conditions.length&&!results.conditions.some(item=>item.condition.condition_id===selectedCondition))setSelectedCondition(results.conditions[0].condition.condition_id);},[results,selectedCondition]);
  const originalAssignments=results?.baseline.missions??[];
  const assignmentKey=selectedAssignment||originalAssignments[0]?.destination_id||"";
  const selectedOriginal=originalAssignments.find(item=>item.destination_id===assignmentKey);
  const fragile=results?.conditions.map(condition=>({label:condition.condition.label,result:condition.original_plan_feasibility.assignments.find(item=>item.destination_id===assignmentKey)})).filter(item=>item.result)??[];
  const overlayRoutes:HypotheticalRoute[]=useMemo(()=>currentStudyEvidence&&selected?.reoptimized_plan.missions?selected.reoptimized_plan.missions.map((mission,index)=>({id:`${mission.unit_id}-${mission.destination_id}`,points:mission.route.polyline_xyz??mission.route.polyline,pointsAreXYZ:Boolean(mission.route.polyline_xyz),color:index%2?"#60cdb8":"#b09aff"})):[],[currentStudyEvidence,selected]);
  const hypotheticalRoadIds=currentStudyEvidence&&selected?.condition.category==="road_closure"?selected.condition.closed_asset_ids:[];
  const hypotheticalBridgeIds=currentStudyEvidence&&selected?.condition.category==="bridge_closure"?selected.condition.closed_asset_ids:[];
  const create=async()=>{
    if(!scenario||!visibleBaseline)return;
    const requestIdentity=liveSnapshotIdentity;
    setBusy(true);setError("");setMessage("");setStudy(null);
    const rainfall=Math.min(300,scenario.parameters.rainfall_mm_h+Math.max(35,scenario.parameters.rainfall_mm_h*.5));
    const conditions:RobustnessCondition[]=[
      {condition_id:"rain-escalation",label:`Rainfall increases to ${rainfall} mm/h`,category:"environment",rainfall_mm_h:rainfall},
      {condition_id:"asset-closure",label:`Hypothetical ${assetKind==="bridge_closure"?"bridge":"road"} closure: ${assets.find(item=>item.id===asset)?.label??asset}`,category:assetKind,closed_asset_ids:asset?[asset]:[]},
      {condition_id:"ambulance-unavailable",label:"One ambulance unavailable",category:"resources",unavailable_unit_type:"ambulance",unavailable_count:1},
      {condition_id:"model-unavailable",label:"Local model unavailable (fallback policy)",category:"ml_reliability",reliability_mode:"injected_unavailable"},
    ];
    try{
      const created=await createRobustnessStudy(scenario.id,visibleBaseline,conditions,Math.max(1,Math.min(12,horizon)),visibleBaseline.plans[0]?.plan_id);
      if(liveSnapshotIdentityRef.current!==requestIdentity)return;
      setStudy(created);setStudyViewIdentity(liveIdentity);setMessage(created.status==="completed"?"Study loaded from the saved identical snapshot.":"Study saved. Computing isolated conditions…");
      let current=created;
      for(let attempt=0;attempt<120&&current.status!=="completed"&&current.status!=="failed"&&current.status!=="interrupted";attempt++){
        await new Promise(resolve=>window.setTimeout(resolve,500));
        current=await fetchRobustnessStudy(created.study_id);
        if(liveSnapshotIdentityRef.current!==requestIdentity)return;
        if(current.scenario_id!==scenarioId||current.scenario_epoch!==scenarioEpoch)throw new Error("The saved study no longer matches the selected scenario snapshot.");
        setStudy(current);
      }
      if(current.status==="failed")setError(current.error??"Study failed.");
      else if(current.status==="completed")setMessage("Saved study complete. All overlays below are hypothetical.");
      else setError("Study is still running. Its saved record can be reopened from this page after refresh.");
    }catch(reason){if(liveSnapshotIdentityRef.current===requestIdentity)setError(reason instanceof Error?reason.message:"Robustness study could not be created.");}
    finally{if(liveSnapshotIdentityRef.current===requestIdentity)setBusy(false);}
  };
  const refreshBaseline=()=>{setStudy(null);setRefreshKey(value=>value+1);};
  return <main className="robustness-page">
    <div className="page-heading"><div><div className="breadcrumb">ANALYTICAL WORKSPACE <ArrowRight size={12}/> DECISION ROBUSTNESS</div><h1>Decision Robustness Lab<span className="heading-dot"/></h1><p>Test how a saved rescue recommendation responds to changed synthetic conditions.</p></div><Badge tone="amber">OFFLINE · ANALYTICAL ONLY</Badge></div>
    <div className="robustness-safety" role="note"><ShieldAlert size={18}/><span>Studies are hypothetical evidence. They do not change the live scenario, missions, resource reservations, road closures, agent outbox, approval, or dispatch.</span></div>
    {error&&<div className="robustness-error" role="alert"><AlertTriangle size={16}/>{error}</div>}
    {message&&<div className="robustness-message" role="status"><CheckCircle2 size={16}/>{message}</div>}
    <div className="robustness-grid">
      <Panel title="Frozen starting point" eyebrow="SNAPSHOT IDENTITY" action={<button className="icon-button" aria-label="Refresh baseline" onClick={refreshBaseline}><RefreshCw size={15}/></button>}>
        {visibleBaseline?<><div className="robustness-facts"><Fact label="Scenario" value={scenario?.name??visibleBaseline.scenario_id}/><Fact label="Tick / epoch" value={`${visibleBaseline.simulation_tick} / ${visibleBaseline.scenario_epoch}`}/><Fact label="State version" value={String(visibleBaseline.simulation_state_version)}/><Fact label="Infrastructure revision" value={String(visibleBaseline.infrastructure_revision)}/><Fact label="Available units" value={String(visibleBaseline.available_unit_ids.length)}/><Fact label="Reserved units" value={String(visibleBaseline.reserved_unit_ids.length)}/><Fact label="Model reliability" value={`${visibleBaseline.model_reliability.status} · ${visibleBaseline.model_reliability.calibration_status}`}/><Fact label="Current eligible proposal" value={visibleBaseline.plans[0]?`${visibleBaseline.plans[0].plan_id.slice(0,12)}… (${visibleBaseline.plans[0].status})`:"Generated at study start"}/></div>{savedStudies.length>0&&<div className="saved-study-list"><strong>Saved studies</strong>{savedStudies.filter(item=>item.scenario_id===scenarioId).map(item=><button key={item.study_id} className={item.stale||item.scenario_epoch!==scenarioEpoch||item.simulation_state_version!==stateVersion?"stale":""} onClick={()=>{if(item.scenario_id!==scenarioId)return;setError("");setMessage("");setStudy(item);setStudyViewIdentity(liveIdentity);}}><span>{item.study_id.slice(0,10)} · {item.status}</span><small>{item.stale||item.scenario_epoch!==scenarioEpoch||item.simulation_state_version!==stateVersion?"Historical snapshot":`tick ${item.simulation_tick} · v${item.simulation_state_version}`} · {item.stale?item.stale_reason:"Open saved results"}</small></button>)}</div>}</>:<p className="muted">Loading the current snapshot…</p>}
      </Panel>
      <Panel title="Build a bounded study" eyebrow="FOUR DETERMINISTIC CONDITIONS">
        <div className="robustness-controls"><label>Infrastructure asset<select value={assetKind} onChange={event=>setAssetKind(event.target.value as "road_closure"|"bridge_closure")}><option value="bridge_closure">Bridge closure</option><option value="road_closure">Road closure</option></select></label><label>Asset<select value={asset} onChange={event=>setAsset(event.target.value)}>{assets.map(item=><option key={item.id} value={item.id}>{item.label}</option>)}</select></label><label>Flood horizon <span>{horizon} ticks · {horizon*5} min synthetic</span><input type="range" min={1} max={12} value={horizon} onChange={event=>setHorizon(Number(event.target.value))}/></label><button className="primary-button" disabled={!visibleBaseline||busy||!scenario||!asset} onClick={create}><FlaskConical size={16}/>{busy?"Computing isolated study…":"Run robustness study"}</button></div>
        {busy&&<div className="study-progress" role="status"><span/>Running the deterministic flood, route, and allocation engines in the background.</div>}
      </Panel>
    </div>
    {displayStudy&&<>
      <div className="study-identity"><Badge tone={displayStudy.stale?"amber":displayStudy.status==="completed"?"green":"neutral"}>{displayStudy.stale?"HISTORICAL SNAPSHOT":displayStudy.status.toUpperCase()}</Badge><span>Study {displayStudy.study_id.slice(0,12)} · SHA-256 {displayStudy.snapshot_sha256.slice(0,16)}…</span>{displayStudy.stale&&<strong>{displayStudy.stale_reason}</strong>}</div>
      {displayStudy.stale&&<div className="robustness-safety" role="note">Historical results belong to this scenario only. Their routes are hidden from the current city view.</div>}
      {results&&<>
        <Panel title="Counterfactual result matrix" eyebrow="MEASURED FROM SAVED COMPUTATIONS" action={<span className="robustness-caption">Rows are deterministic conditions; no likelihood weighting</span>}>
          <div className="robustness-table-wrap"><table className="robustness-table"><thead><tr><th>Condition</th><th>Original routes supported by synthetic graph</th><th>Unsupported</th><th>Replanned graph-supported assignments</th><th>Priority coverage / eligible points</th><th>Synthetic travel sum</th><th>Reliability</th></tr></thead><tbody>{results.conditions.map(item=><tr key={item.condition.condition_id} className={selected?.condition.condition_id===item.condition.condition_id?"selected":""} onClick={()=>setSelectedCondition(item.condition.condition_id)}><th>{item.condition.label}<small>{item.condition.category}</small></th><td>{item.original_plan_feasibility.feasible_assignments}/{item.original_plan_feasibility.total_original_assignments}</td><td>{item.original_plan_feasibility.invalidated_routes}</td><td>{item.reoptimized_plan.metrics.assigned_destinations}</td><td>{item.reoptimized_plan.metrics.priority_weighted_coverage.toFixed(1)} / {item.reoptimized_plan.metrics.coverage_denominator_priority_points.toFixed(1)}</td><td>{item.reoptimized_plan.metrics.sum_synthetic_travel_minutes.toFixed(1)} min</td><td>{item.reliability.status}</td></tr>)}</tbody></table></div>
          <p className="robustness-caption">Route support means connected, traversable geometry under this synthetic graph, depth limits, and documented access-spur assumptions. It does not establish surveyed-road access or emergency field safety. Coverage is existing priority score × occupant-capacity fraction. Denominators use each condition’s own eligible destinations; environmental changes can change those priorities.</p>
        </Panel>
        <div className="robustness-grid">
          <Panel title="Hypothetical city overlay" eyebrow="COUNTERFACTUAL ROUTES ONLY"><div className="robustness-scene-label">HYPOTHETICAL · NO MISSION ANIMATION OR LIVE STATUS CHANGE</div><p className="robustness-caption">The 3D water layer shows the live baseline. Flood differences for this hypothetical condition are reported in computed metrics; no hypothetical water geometry is drawn.</p>{!currentStudyEvidence&&<p className="robustness-caption">Historical route overlays are suppressed because this study does not match the exact live scenario epoch, version, and infrastructure revision.</p>}<div className="robustness-scene"><Suspense fallback={<div className="muted">Loading the shared city scene…</div>}><LazyCityScene city={city} scenario={scenario} selected={null} onSelect={()=>undefined} layers={layers} lowGraphics={true} predictions={null} routeLines={[]} manualClosureIds={[]} missions={[]} missionUnits={[]} selectedMissionId={null} onSelectMission={()=>undefined} hypotheticalRoutes={overlayRoutes} hypotheticalClosedRoadIds={hypotheticalRoadIds} hypotheticalClosedBridgeIds={hypotheticalBridgeIds}/></Suspense></div><div className="robustness-legend"><span><i className="route-key purple"/>Reoptimized route</span><span><i className="route-key amber"/>Hypothetical closure</span></div></Panel>
          <Panel title="Fragility inspector" eyebrow="ORIGINAL PLAN, NOT SILENTLY REASSIGNED"><label className="inspector-select">Original assignment<select value={assignmentKey} onChange={event=>setSelectedAssignment(event.target.value)}>{originalAssignments.map(item=><option key={`${item.unit_id}-${item.destination_id}`} value={item.destination_id}>{item.unit_id} → {item.destination_id}</option>)}</select></label>{selectedOriginal?<div className="fragility-list">{fragile.map(item=><article key={item.label}><strong>{item.label}</strong><Badge tone={item.result?.original_route_feasible?"green":"amber"}>{item.result?.original_route_feasible?"SUPPORTED":"NOT SUPPORTED"}</Badge><p>{item.result?.failure_reasons.length?item.result.failure_reasons.join(" "):"Saved route is supported under the frozen synthetic graph and resource assumptions; this is not field-verified access."}</p></article>)}</div>:<p className="muted">The frozen plan has no assigned destinations to inspect.</p>}</Panel>
        </div>
        <div className="robustness-grid">
          <Panel title="Critical infrastructure dependencies" eyebrow="PERTURBATION-BASED RANKING"><p className="robustness-caption">Ranking reflects connections and route segments in this synthetic graph, not surveyed infrastructure access.</p>{results.critical_infrastructure.length?<div className="dependency-list">{results.critical_infrastructure.map(item=><article key={item.asset_id}><strong>{item.asset_id}</strong><span>{item.dependent_assignments} original assignments depend on it under the frozen graph</span><small>{item.affected_priority_weighted_coverage.toFixed(1)} affected priority points · alternate graph route {item.feasible_after_closure?"observed":"not observed"}</small></article>)}</div>:<p className="muted">No original assignment traverses a ranked road or bridge, or the baseline has no assigned routes.</p>}</Panel>
          <Panel title="Contingency suggestions" eyebrow="COMMANDER REVIEW REQUIRED">{results.contingencies.length?<div className="dependency-list">{results.contingencies.slice(0,8).map(item=><article key={item.contingency_id}><strong>{item.trigger_condition}</strong><span>{item.unit_id} → {item.destination_id} · {item.route.distance_m.toFixed(0)} m</span><small>Supported under the saved synthetic graph assumptions only; not surveyed or field-verified. Not applied to live operations.</small></article>)}</div>:<p className="muted">No supported changed assignment was produced. The study reports infeasibility without manufacturing an alternative.</p>}</Panel>
        </div>
        <Panel title="Reliability and reproduction" eyebrow="SYNTHETIC MODEL EVIDENCE"><p>{results.interpretation}</p><div className="reproduction-row"><span>Seed {displayStudy.seed}</span><span>Algorithm {displayStudy.algorithm_version}</span><span>Horizon {displayStudy.evaluation_horizon_ticks} ticks</span><span>Runtime {results.study_runtime_ms.toFixed(1)} ms</span><span>{displayStudy.reproduction.isolation as string}</span></div>{selected?.reliability.warnings.map(warning=><p className="robustness-caption" key={warning}><AlertTriangle size={13}/>{warning}</p>)}</Panel>
      </>}
    </>}
    <div className="robustness-footnote"><Activity size={14}/> Synthetic scenario evidence only. Rescue routes are not field-safety determinations; commanders must create and validate a fresh live proposal before any approval.</div>
  </main>;
}

function Fact({label,value}:{label:string;value:string}){return <div className="robustness-fact"><span>{label}</span><strong>{value}</strong></div>;}
