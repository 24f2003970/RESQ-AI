import { lazy, Suspense, useEffect, useMemo, useRef, useState, type ComponentProps } from "react";
import { AlertTriangle, Download, FlaskConical, Play, Square, Waves } from "lucide-react";
import {
  cancelScenarioExperiment, createScenarioExperiment, fetchCityForSeed,
  fetchScenarioExperiment, fetchScenarioExperiments,
  type CityState, type ScenarioExperiment, type ScenarioExperimentCreate,
  type ScenarioState,
} from "../api/client";
import type { Layers } from "../scene/CityScene";
import { Badge, Panel } from "./ui";

type VariantDraft = {
  preset: "" | "mild" | "heavy" | "extreme";
  rainfall: number;
  river: number;
  drainage: number;
  ambulances: number;
  teams: number;
  roads: string[];
};
type TrendPoint = { tick: number; simulated_minutes: number; maximum_flood_depth_m: number; flood_affected_buildings: number; exposed_roads: number; closed_bridges: number };
type AssignmentMetrics = { destinations_covered:number; priority_weighted_coverage:number; occupants_targeted:number; total_distance_m:number; total_simulated_travel_minutes:number; maximum_estimated_arrival_minutes:number; resource_utilization:number; unreachable_destinations:number; objective_value:number; available_unit_count:number; reserved_unit_count:number };
type ExperimentVariantResult = {
  variant_id:"A"|"B"; label:string; configuration:Record<string,unknown>; final_state:ScenarioState;
  time_series:TrendPoint[]; summary:TrendPoint; high_priority_destinations:number; high_priority_threshold_score:number;
  reachable_rescue_destinations:number; reachable_destination_ids:string[]; unreachable_destinations:unknown[];
  resource_availability:{ambulances:number;ground_teams:number;available_unit_count:number;reserved_unit_count:number};
  route_comparison:{baseline:AssignmentMetrics;optimized:AssignmentMetrics};
  optimized_vs_conventional_deltas:Record<string,{baseline:number;optimized:number;absolute_optimized_minus_baseline:number;relative_percent_vs_baseline:number|null}>;
  optimized_missions:Array<{unit_id:string;destination_id:string;route:{distance_m:number;simulated_minutes:number;polyline:number[][];road_ids:string[]}}>;
  conventional_missions:Array<{unit_id:string;destination_id:string;route:{distance_m:number;simulated_minutes:number}}>;
  objective:string;solver_status:string;machine_learning:{status:string;model_version:string|null;uncalibrated:boolean;unavailable_reason:string|null};
  manual_closure_road_ids:string[];timings_ms:Record<string,number>;
};
type ExperimentResults={variants:ExperimentVariantResult[];comparison:{deltas:Record<string,{variant_a:number;variant_b:number;absolute_b_minus_a:number;relative_percent_b_vs_a:number|null}>;explanations:string[];fairness:string};experiment_runtime_ms:number;payload_bytes:number};
const PRESET_PARAMETERS={mild:{rainfall:8,river:-0.5,drainage:0.8},heavy:{rainfall:90,river:0.25,drainage:0.45},extreme:{rainfall:180,river:1.4,drainage:0.2}} as const;

const LazyScene = lazy(() => import("../scene/CityScene"));
const sceneLayers: Layers = {buildings:true,greenery:true,facilities:true,districts:false,units:true,flood:true,infrastructure:true,predictedRisk:false};
const METRICS:Record<string,{title:string;definition:string;inputs:string;formula:string;source:string;algorithm:string;limitations:string}>={
  maximum_flood_depth_m:{title:"Maximum flood depth",definition:"Highest land-cell water depth in the final simulated state.",inputs:"Backend depth grid and channel mask.",formula:"max(depth_m) over non-channel cells.",source:"Saved final ScenarioState; meters.",algorithm:"Existing deterministic flood grid.",limitations:"Simplified synthetic process model, not a hydraulic forecast."},
  flood_affected_buildings:{title:"Flood-affected buildings",definition:"Buildings whose simulated water depth crosses the existing physical exposure threshold.",inputs:"Final depth grid, generated footprints, river stage.",formula:"Count of buildings with water_reaches_building = true.",source:"Backend physical impact assessment; buildings.",algorithm:"Existing impact_assessment function.",limitations:"Physical exposure is separate from the ML future-risk prediction."},
  exposed_roads:{title:"Exposed roads",definition:"Road corridors in caution or flooded state at the selected tick.",inputs:"Final depth grid and road thresholds.",formula:"Count of roads with status caution or flooded.",source:"Backend physical impact assessment; corridors.",algorithm:"Existing road exposure rules.",limitations:"Manual closures are reported separately from flood exposure."},
  closed_bridges:{title:"Closed bridges",definition:"Bridge crossings closed by simulated water relative to deck height.",inputs:"Water surface and generated bridge deck elevations.",formula:"Count of bridge impacts with status closed.",source:"Backend physical impact assessment; bridges.",algorithm:"Existing bridge threshold rule.",limitations:"No structural damage or traffic model."},
  priority_weighted_coverage:{title:"Priority-weighted coverage",definition:"Sum of destination priority weighted by the fraction of occupants targeted within unit capacity.",inputs:"Destination priority scores, occupants, unit capacities, valid routes.",formula:"Σ priority_score × min(unit_capacity, occupants) / max(occupants, 1).",source:"Saved rescue plan comparison; score points.",algorithm:"SciPy maximum-weight assignment or priority-ordered nearest-unit baseline.",limitations:"Priorities and capacities are synthetic; this single objective does not optimize every metric independently."},
  total_distance_m:{title:"Total route distance",definition:"Sum of assigned graph-route distances.",inputs:"Selected missions and route polylines.",formula:"Σ route.distance_m.",source:"NetworkX routes; meters.",algorithm:"Dijkstra-derived compatible route graph.",limitations:"Straight-line access spurs and synthetic road speeds; no live traffic."},
  total_simulated_travel_minutes:{title:"Total synthetic travel time",definition:"Sum of estimated route travel minutes over assigned units.",inputs:"Route edge lengths and assumed speeds.",formula:"Σ route.simulated_minutes.",source:"Computed rescue missions; minutes.",algorithm:"Route-edge length divided by declared synthetic speed.",limitations:"This sum is not the maximum estimated arrival time and is not a traffic ETA."},
  maximum_estimated_arrival_minutes:{title:"Maximum estimated arrival",definition:"Largest synthetic route time among assigned missions.",inputs:"Computed mission route times.",formula:"max(route.simulated_minutes), or 0 with no missions.",source:"Computed rescue missions; minutes.",algorithm:"Maximum across assignment routes.",limitations:"Synthetic travel assumption, not a dispatch ETA."},
  resource_utilization:{title:"Resource utilization",definition:"Share of configured available ground units assigned by a method.",inputs:"Assigned units and available experiment inventory.",formula:"assigned units / available units; 0 when none are available.",source:"Experiment resource configuration and allocation.",algorithm:"Constrained assignment.",limitations:"Experimental resources are isolated and never reserved operationally."},
  objective_value:{title:"Declared assignment objective",definition:"Optimization trade-off value for the assignment.",inputs:"Priority-weighted occupant coverage and total synthetic travel minutes.",formula:"priority_weighted_coverage − 0.15 × total_simulated_travel_minutes.",source:"Actual baseline or optimized assignment.",algorithm:"Maximum-weight assignment objective.",limitations:"A higher objective does not imply every travel or coverage metric improves."},
};

function defaultDraft(scenario:ScenarioState, variant:"A"|"B"):VariantDraft {
  return {preset:"",rainfall:variant==="A"?scenario.parameters.rainfall_mm_h:Math.min(300,scenario.parameters.rainfall_mm_h+90),
    river:variant==="A"?scenario.parameters.river_level_m:Math.min(5,scenario.parameters.river_level_m+0.8),
    drainage:variant==="A"?scenario.parameters.drainage_effectiveness:Math.max(0,scenario.parameters.drainage_effectiveness-0.25),
    ambulances:2,teams:2,roads:[]};
}

function TrendChart({title,unit,series}:{title:string;unit:string;series:Array<{label:string;color:string;points:TrendPoint[];key:keyof TrendPoint}>}) {
  const width=620,height=190,left=42,right=14,top=12,bottom=30;
  const values=series.flatMap(s=>s.points.map(p=>Number(p[s.key]))).filter(Number.isFinite);
  const max=Math.max(...values,0),min=Math.min(...values,0),range=max-min||1;
  const px=(index:number,length:number)=>left+(length<2?0:index*(width-left-right)/(length-1));
  const py=(value:number)=>top+(max-value)*(height-top-bottom)/range;
  return <figure className="experiment-chart"><figcaption>{title}<small>{unit}</small></figcaption><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
    {[0,.5,1].map(r=><g key={r}><line x1={left} x2={width-right} y1={top+r*(height-top-bottom)} y2={top+r*(height-top-bottom)} stroke="#344744"/><text x={4} y={top+r*(height-top-bottom)+4} fill="#91a49f" fontSize="10">{(max-r*range).toFixed(1)}</text></g>)}
    {series.map(s=><g key={s.label}><polyline fill="none" stroke={s.color} strokeWidth="2.5" points={s.points.map((p,i)=>`${px(i,s.points.length)},${py(Number(p[s.key]))}`).join(" ")}/>{s.points.map((p,i)=><circle key={`${s.label}-${p.tick}`} cx={px(i,s.points.length)} cy={py(Number(p[s.key]))} r="2.5" fill={s.color}/>)}</g>)}
    <text x={left} y={height-6} fill="#91a49f" fontSize="10">Start</text><text x={width-right} y={height-6} textAnchor="end" fill="#91a49f" fontSize="10">End of horizon</text>
  </svg><div className="experiment-chart-legend">{series.map(s=><span key={s.label}><i style={{background:s.color}}/>{s.label}</span>)}</div></figure>;
}

function ResourceChart({variants}:{variants:ExperimentVariantResult[]}) {
  const points=variants.flatMap((v)=>[
    {label:`${v.variant_id} · conventional`,x:v.resource_availability.available_unit_count,y:v.route_comparison.baseline.priority_weighted_coverage,color:"#c9ad7b"},
    {label:`${v.variant_id} · optimized`,x:v.resource_availability.available_unit_count,y:v.route_comparison.optimized.priority_weighted_coverage,color:"#6dd6c1"},
  ]);
  const maxX=Math.max(...points.map(p=>p.x),1),maxY=Math.max(...points.map(p=>p.y),1);
  return <figure className="experiment-chart"><figcaption>Coverage versus available resources<small>Priority-weighted score points · x = available units</small></figcaption><svg viewBox="0 0 620 190" role="img" aria-label="Coverage versus available resources">
    {[0,.5,1].map(r=><g key={r}><line x1="48" x2="605" y1={12+r*145} y2={12+r*145} stroke="#344744"/><text x="4" y={16+r*145} fill="#91a49f" fontSize="10">{(maxY*(1-r)).toFixed(1)}</text></g>)}
    {points.map(p=><g key={p.label}><circle cx={48+p.x/maxX*550} cy={157-p.y/maxY*145} r="5" fill={p.color}/><text x={52+p.x/maxX*550} y={154-p.y/maxY*145} fill="#dce6e1" fontSize="9">{p.label}</text></g>)}
    <text x="325" y="184" textAnchor="middle" fill="#91a49f" fontSize="10">Available experiment units</text>
  </svg></figure>;
}

function MetricBars({title,metric,variants}:{title:string;metric:"total_distance_m"|"total_simulated_travel_minutes";variants:ExperimentVariantResult[]}) {
  const data=variants.flatMap(v=>[
    {label:`${v.variant_id} conventional`,value:v.route_comparison.baseline[metric],color:"#c9ad7b"},
    {label:`${v.variant_id} RESQ-AI`,value:v.route_comparison.optimized[metric],color:"#6dd6c1"},
  ]);
  const max=Math.max(...data.map(p=>p.value),1);
  return <figure className="experiment-chart"><figcaption>{title}<small>{metric==="total_distance_m"?"m":"sum of synthetic route minutes"}</small></figcaption><svg viewBox="0 0 620 170" role="img" aria-label={title}>{data.map((p,i)=><g key={p.label}><text x="4" y={26+i*35} fill="#b9c8c2" fontSize="10">{p.label}</text><rect x="150" y={12+i*35} width={430*p.value/max} height="20" rx="4" fill={p.color}/><text x={156+430*p.value/max} y={27+i*35} fill="#f0f4ef" fontSize="10">{p.value.toFixed(1)}</text></g>)}</svg></figure>;
}

function ExperimentTwin({record,variant}:{record:ScenarioExperiment;variant:ExperimentVariantResult}) {
  const [city,setCity]=useState<CityState|null>(null);const [error,setError]=useState("");
  const result=variant.final_state;
  useEffect(()=>{let live=true;fetchCityForSeed(record.base_seed).then(value=>{if(live)setCity(value)}).catch(reason=>{if(live)setError(reason instanceof Error?reason.message:"Could not load city geometry.")});return()=>{live=false}},[record.base_seed]);
  if(error)return <p className="experiment-error" role="alert">{error}</p>;
  if(!city)return <p className="scenario-note">Loading the local Digital Twin…</p>;
  const routes=variant.optimized_missions.map(mission=>mission.route.polyline);
  const props:ComponentProps<typeof LazyScene>={city,scenario:result,selected:null,onSelect:()=>{},layers:sceneLayers,lowGraphics:true,predictions:null,routeLines:routes,manualClosureIds:variant.manual_closure_road_ids,missions:[],missionUnits:[],selectedMissionId:null,onSelectMission:()=>{}};
  return <div className="experiment-twin"><div className="experiment-twin-label"><Badge>{variant.variant_id} · {variant.label}</Badge><span>Tick {result.tick} · {result.parameters.rainfall_mm_h} mm/h · river {result.parameters.river_level_m.toFixed(2)} m</span></div><Suspense fallback={<div className="scene-loading">Preparing the saved flood snapshot…</div>}><LazyScene {...props}/></Suspense></div>;
}

export default function ScenarioComparison({scenario,city}:{scenario:ScenarioState;city:CityState}) {
  const [a,setA]=useState(()=>defaultDraft(scenario,"A"));const [b,setB]=useState(()=>defaultDraft(scenario,"B"));
  const scenarioRef=useRef(scenario);scenarioRef.current=scenario;
  const [ticks,setTicks]=useState(6);const [record,setRecord]=useState<ScenarioExperiment|null>(null);
  const [saved,setSaved]=useState<ScenarioExperiment[]>([]);const [error,setError]=useState("");const [busy,setBusy]=useState(false);
  const [metric,setMetric]=useState("priority_weighted_coverage");const [twinVariant,setTwinVariant]=useState<"A"|"B">("A");
  useEffect(()=>{setA(defaultDraft(scenarioRef.current,"A"));setB(defaultDraft(scenarioRef.current,"B"));setRecord(null)},[scenario.id]);
  useEffect(()=>{let live=true;fetchScenarioExperiments(scenario.id).then(rows=>{if(live)setSaved(rows)}).catch(()=>{});return()=>{live=false}},[scenario.id,record?.status]);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- Polling is keyed by the experiment ID/status; the captured record provides those exact values.
  useEffect(()=>{if(!record||!(["pending","running","cancel_requested"].includes(record.status)))return;let live=true;const poll=()=>void fetchScenarioExperiment(record.experiment_id).then(next=>{if(live)setRecord(next)}).catch(reason=>{if(live)setError(reason instanceof Error?reason.message:"Experiment status could not be refreshed.")});const timer=window.setInterval(poll,750);return()=>{live=false;window.clearInterval(timer)}},[record?.experiment_id,record?.status]);
  const results=record?.results as unknown as ExperimentResults|undefined;
  const variants=results?.variants;
  const twin=variants?.find(item=>item.variant_id===twinVariant)??variants?.[0];
  const draftCard=(label:"A"|"B",draft:VariantDraft,setter:(value:VariantDraft)=>void)=><div className="experiment-variant-card">
    <div className="experiment-variant-heading"><Badge>{label}</Badge><strong>Variant {label}</strong><small>{label==="A"?"Reference conditions":"Alternative conditions"}</small></div>
    <label className="experiment-field">Preset<select value={draft.preset} onChange={e=>{const preset=e.target.value as VariantDraft["preset"];setter({...draft,preset,...(preset?PRESET_PARAMETERS[preset]:{})})}}><option value="">Use saved baseline</option><option value="mild">Mild</option><option value="heavy">Heavy</option><option value="extreme">Extreme</option></select></label>
    <label className="experiment-field">Rainfall <b>{draft.rainfall} mm/h</b><input type="range" min="0" max="300" step="5" value={draft.rainfall} onChange={e=>setter({...draft,rainfall:Number(e.target.value)})}/></label>
    <label className="experiment-field">River stage <b>{draft.river.toFixed(2)} m</b><input type="range" min="-2" max="5" step="0.05" value={draft.river} onChange={e=>setter({...draft,river:Number(e.target.value)})}/></label>
    <label className="experiment-field">Drainage effectiveness <b>{Math.round(draft.drainage*100)}%</b><input type="range" min="0" max="1" step="0.05" value={draft.drainage} onChange={e=>setter({...draft,drainage:Number(e.target.value)})}/></label>
    <div className="experiment-resource-row"><label>Ambulances<select value={draft.ambulances} onChange={e=>setter({...draft,ambulances:Number(e.target.value)})}><option value={0}>0</option><option value={1}>1</option><option value={2}>2</option></select></label><label>Ground teams<select value={draft.teams} onChange={e=>setter({...draft,teams:Number(e.target.value)})}><option value={0}>0</option><option value={1}>1</option><option value={2}>2</option></select></label></div>
    <label className="experiment-field">Manual road closures <select multiple value={draft.roads} onChange={e=>setter({...draft,roads:Array.from(e.currentTarget.selectedOptions,o=>o.value)})} aria-label={`Variant ${label} road closures`}>{city.roads.map(road=><option key={road.id} value={road.id}>{road.name} · {road.id}</option>)}</select><small>Use Ctrl/Command to select multiple roads.</small></label>
  </div>;
  async function run() {
    if(busy)return;setBusy(true);setError("");
    const toVariant=(id:"A"|"B",value:VariantDraft)=>({variant_id:id,label:id==="A"?"Variant A":"Variant B",...(value.preset?{preset:value.preset}:{}),rainfall_mm_h:value.rainfall,river_level_m:value.river,drainage_effectiveness:value.drainage,available_ambulances:value.ambulances,available_ground_teams:value.teams,closed_road_ids:value.roads});
    const body:ScenarioExperimentCreate={name:`${scenario.name} · A/B`,base_scenario_id:scenario.id,expected_state_version:scenario.state_version,simulation_ticks:ticks,variants:[toVariant("A",a),toVariant("B",b)]};
    try{const next=await createScenarioExperiment(scenario.id,body);setRecord(next)}catch(reason){setError(reason instanceof Error?reason.message:"Could not start the experiment.")}finally{setBusy(false)}
  }
  async function cancel(){if(!record)return;try{setRecord(await cancelScenarioExperiment(record.experiment_id))}catch(reason){setError(reason instanceof Error?reason.message:"Could not cancel the experiment.")}}
  function exportJson(){if(!record)return;const blob=new Blob([JSON.stringify(record,null,2)],{type:"application/json"});const url=URL.createObjectURL(blob);const anchor=document.createElement("a");anchor.href=url;anchor.download=`resq-experiment-${record.experiment_id}.json`;anchor.click();URL.revokeObjectURL(url)}
  const selectedMetric=METRICS[metric];
  const chartSeries=useMemo(()=>variants?.map(v=>({label:`Variant ${v.variant_id}`,color:v.variant_id==="A"?"#c9ad7b":"#6dd6c1",points:v.time_series}))??[],[variants]);
  return <section className="scenario-experiment-lab" aria-label="Scenario comparison experiment">
    <div className="experiment-section-heading"><div><span className="eyebrow">REPRODUCIBLE WHAT-IF EXPERIMENT</span><h2>Scenario Intelligence Lab</h2><p>Both variants start from the same saved flood snapshot and seed. Only the settings shown here differ.</p></div><Badge>{record?.status??"Ready"}</Badge></div>
    <Panel title="Scenario builder" eyebrow={`BASE SNAPSHOT · ${scenario.name}`} action={<FlaskConical size={17}/> }>
      <div className="experiment-base-line"><span>Seed {scenario.seed} · tick {scenario.tick} · version {scenario.state_version} · epoch {scenario.epoch}</span><span>Shared start · same simulation horizon</span></div>
      <div className="experiment-builder-grid">{draftCard("A",a,setA)}{draftCard("B",b,setB)}</div>
      <div className="experiment-run-row"><label>Additional simulation horizon <strong>{ticks} ticks · {ticks*5} minutes</strong><input type="range" min="0" max="120" step="1" value={ticks} onChange={e=>setTicks(Number(e.target.value))}/><small>0 ticks compares interventions against the current physical snapshot.</small></label><div><button className="primary-button" disabled={busy||["pending","running","cancel_requested"].includes(record?.status??"")} onClick={()=>void run()}><Play size={15}/>{busy?"Starting…":"Run A/B comparison"}</button>{record&&["pending","running","cancel_requested"].includes(record.status)&&<button className="secondary-button" onClick={()=>void cancel()}><Square size={14}/> Cancel experiment</button>}</div></div>
      {record&&["pending","running","cancel_requested"].includes(record.status)&&<div className="experiment-progress"><div><span>{record.status===`cancel_requested`?"Cancelling after the current simulation step":`Running Variant ${record.current_variant??"A/B"}`}</span><b>{record.progress_percent.toFixed(0)}%</b></div><progress max="100" value={record.progress_percent}/></div>}
      {error&&<div className="experiment-error" role="alert"><AlertTriangle size={16}/>{error}</div>}
      {record?.status==="failed"&&<p className="experiment-error" role="alert">{record.error}</p>}
      {record?.status==="interrupted"&&<p className="experiment-error" role="alert">{record.error}</p>}
      {saved.length>0&&<label className="experiment-saved">Saved experiment<select value={record?.experiment_id??""} onChange={e=>{const found=saved.find(item=>item.experiment_id===e.target.value);if(found)setRecord(found)}}><option value="">Select a saved run…</option>{saved.map(item=><option key={item.experiment_id} value={item.experiment_id}>{item.name} · {item.status} · {new Date(item.created_at_utc).toLocaleString()}</option>)}</select></label>}
    </Panel>
    {record?.status==="completed"&&results&&variants&&<>
      <div className="experiment-section-heading"><div><span className="eyebrow">SAVED COMPUTED OUTPUTS</span><h2>Comparison results</h2><p>Experiment {record.experiment_id.slice(0,12)} · {String(record.reproduction.physical_engine)} · {record.simulation_ticks*5} simulated minutes</p></div><button className="secondary-button" onClick={exportJson}><Download size={15}/> Export JSON</button></div>
      <Panel title="Measured scenario outcomes" eyebrow="SAME BASE SNAPSHOT · UNIT-ANALYSIS ONLY"><div className="experiment-results-table"><table><thead><tr><th>Outcome</th><th>Variant A · {variants[0].label}</th><th>Variant B · {variants[1].label}</th><th>B − A</th></tr></thead><tbody>{[["Maximum flood depth","maximum_flood_depth_m","m"],["Affected buildings","flood_affected_buildings",""],["Exposed roads","exposed_roads",""],["Closed bridges","closed_bridges",""],["High-priority destinations","high_priority_destinations",""],["Reachable rescue destinations","reachable_rescue_destinations",""]].map(([label,key,suffix])=>{const av=key==="high_priority_destinations"?variants[0].high_priority_destinations:key==="reachable_rescue_destinations"?variants[0].reachable_rescue_destinations:variants[0].summary[key as keyof TrendPoint];const bv=key==="high_priority_destinations"?variants[1].high_priority_destinations:key==="reachable_rescue_destinations"?variants[1].reachable_rescue_destinations:variants[1].summary[key as keyof TrendPoint];const delta=Number(bv)-Number(av);return <tr key={key}><th>{label}</th><td>{Number(av).toFixed(key==="maximum_flood_depth_m"?2:0)}{suffix}</td><td>{Number(bv).toFixed(key==="maximum_flood_depth_m"?2:0)}{suffix}</td><td>{delta>0?"+":""}{delta.toFixed(key==="maximum_flood_depth_m"?2:0)}{suffix}</td></tr>})}</tbody></table></div>
        <div className="experiment-allocation-grid">{variants.map(v=><div key={v.variant_id} className="experiment-allocation-card"><h3>Variant {v.variant_id} · {v.label}</h3><div className="experiment-allocation-columns">{(["baseline","optimized"] as const).map(method=>{const data=v.route_comparison[method];return <div key={method}><Badge tone={method==="optimized"?"green":""}>{method==="optimized"?"RESQ-AI optimized":"Conventional nearest"}</Badge><dl><dt>Destinations covered</dt><dd>{data.destinations_covered}</dd><dt>Priority-weighted coverage</dt><dd>{data.priority_weighted_coverage.toFixed(2)} pts</dd><dt>Occupants targeted</dt><dd>{data.occupants_targeted}</dd><dt>Resources used / available</dt><dd>{Math.round(data.resource_utilization*data.available_unit_count)} / {data.available_unit_count}</dd><dt>Unreachable priorities</dt><dd>{data.unreachable_destinations}</dd><dt>Objective value</dt><dd>{data.objective_value.toFixed(2)}</dd></dl></div>})}</div><p className="scenario-note">The same valid routes, compatible inventory, unit capacities, destination scores and constraints are given to both methods.</p></div>)}</div>
        <div className="experiment-explanations">{results.comparison.explanations.map((line,i)=><p key={i}><Waves size={15}/>{line}</p>)}{!results.comparison.explanations.length&&<p>No measured difference crossed the displayed scenario metrics in this run.</p>}</div>
      </Panel>
      <Panel title="Evidence charts" eyebrow="PERSISTED EXPERIMENT TIME SERIES">
        <div className="experiment-chart-grid">
          <TrendChart title="Flood depth evolution" unit="maximum land depth · meters" series={chartSeries.map(s=>({...s,key:"maximum_flood_depth_m" as const}))}/>
          <TrendChart title="Affected buildings" unit="count at each saved tick" series={chartSeries.map(s=>({...s,key:"flood_affected_buildings" as const}))}/>
          <TrendChart title="Infrastructure exposure" unit="roads or bridges · counts" series={chartSeries.flatMap(s=>[{...s,label:`${s.label} roads`,color:s.label.includes("A")?"#d9ae6f":"#63c8b6",key:"exposed_roads" as const},{...s,label:`${s.label} bridges`,color:s.label.includes("A")?"#9b835c":"#438d83",key:"closed_bridges" as const}])}/>
          <ResourceChart variants={variants}/>
          <MetricBars title="Assigned route distance" metric="total_distance_m" variants={variants}/>
          <MetricBars title="Total route-time sum" metric="total_simulated_travel_minutes" variants={variants}/>
        </div>
        <p className="scenario-note">Route-time sum is shown separately from maximum estimated arrival time. Every plotted point comes from this saved experiment.</p>
      </Panel>
      <div className="experiment-twin-panel"><Panel title="One-canvas A/B Digital Twin" eyebrow="CAMERA PRESERVED WHILE SWITCHING"><div className="experiment-switcher">{variants.map(v=><button key={v.variant_id} className={twinVariant===v.variant_id?"selected":""} onClick={()=>setTwinVariant(v.variant_id)}>Variant {v.variant_id} · {v.label}</button>)}</div>{twin&&<ExperimentTwin record={record} variant={twin}/>}</Panel></div>
      <Panel title="Comparison inspector" eyebrow="METRIC DEFINITION & PROVENANCE"><label className="experiment-field">Choose a metric<select value={metric} onChange={e=>setMetric(e.target.value)}>{Object.entries(METRICS).map(([key,item])=><option key={key} value={key}>{item.title}</option>)}</select></label>{selectedMetric&&<div className="experiment-inspector"><h3>{selectedMetric.title}</h3><p>{selectedMetric.definition}</p><dl>{([["Inputs",selectedMetric.inputs],["Formula",selectedMetric.formula],["Source data",selectedMetric.source],["Algorithm",selectedMetric.algorithm],["Limitations",selectedMetric.limitations]] as const).map(([key,value])=><div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl>{variants.map(v=><p key={v.variant_id} className="experiment-inspector-value">Variant {v.variant_id}: {metric==="priority_weighted_coverage"||metric==="objective_value"||metric==="resource_utilization"?v.route_comparison.optimized[metric as keyof AssignmentMetrics]:v.summary[metric as keyof TrendPoint]??"—"}</p>)}</div>}</Panel>
      <Panel title="Reproduction & run health" eyebrow="LOCAL PERFORMANCE"><p>{results.comparison.fairness}</p><div className="experiment-performance-grid">{variants.map(v=><div key={v.variant_id}><b>Variant {v.variant_id}</b><span>Flood simulation {v.timings_ms.flood_simulation?.toFixed(1)??"—"} ms</span><span>ML inference {v.timings_ms.ml_inference?.toFixed(1)??"—"} ms · {v.machine_learning.status}</span><span>Routing {v.timings_ms.routing?.toFixed(1)??"—"} ms</span><span>Assignment {v.timings_ms.assignment?.toFixed(1)??"—"} ms</span><span>Variant wall {v.timings_ms.variant_wall?.toFixed(1)??"—"} ms</span></div>)}<div><b>Persisted experiment</b><span>Total runtime {results.experiment_runtime_ms.toFixed(1)} ms</span><span>JSON payload {results.payload_bytes.toLocaleString()} bytes</span><span>Solver {variants[0].solver_status}</span></div></div>{variants.some(v=>v.machine_learning.status==="unavailable")&&<p className="experiment-error"><AlertTriangle size={15}/> Local model unavailable: physical exposure and rescue routes still come from backend rules; no ML prediction was fabricated.</p>}</Panel>
    </>}
    <p className="scenario-disclaimer">ANALYTICAL EXPERIMENT · ISOLATED SQLITE NAMESPACE · NO LIVE PLANS OR RESOURCE RESERVATIONS</p>
  </section>;
}
