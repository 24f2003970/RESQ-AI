import { useCallback, useEffect, useRef, useState } from "react";
import { Panel, Badge } from "./ui";
import { fetchLatestRecommendation, type CityState, type ScenarioState } from "../api/client";

export type Plan = {
  plan_id:string; scenario_id:string; scenario_epoch?:number; scenario_version:number; simulation_tick:number; status:string;
  priorities:{building_id:string;name:string;priority_score:number;explanation:string}[];
  missions:{unit_id:string;destination_id:string;unit_capacity:number;occupants_targeted:number;route:{distance_m:number;simulated_minutes:number;road_ids:string[];polyline:number[][]}}[];
  available_assignments:{unit_id:string;destination_id:string;unit_capacity:number;occupants_targeted:number;route:{distance_m:number;simulated_minutes:number;road_ids:string[];polyline:number[][]}}[];
  unreachable:{building_id:string;reason:string}[]; comparison:{baseline:Record<string,number>;optimized:Record<string,number>};
  solver_status:string; objective:string; explanation:string;
};

export default function RescuePlanning({city,scenario,onPlan}:{city:CityState;scenario:ScenarioState|null;onPlan:(plan:Plan|null)=>void}) {
  const [plan,setPlanLocal]=useState<Plan|null>(null); const [assignmentKeys,setAssignmentKeys]=useState<Record<number,string>>({}); const setPlan=useCallback((p:Plan|null)=>{setPlanLocal(p);onPlan(p);setAssignmentKeys(Object.fromEntries((p?.missions??[]).map((m,i)=>[i,`${m.unit_id}|${m.destination_id}`])));},[onPlan]); const [busy,setBusy]=useState(false); const [error,setError]=useState("");
  const planRef=useRef<Plan|null>(null);planRef.current=plan;
  const scenarioId=scenario?.id;
  const [road,setRoad]=useState(city.roads[0]?.id??"");
  const call=useCallback(async(path:string,init?:RequestInit) => {
    const response=await fetch(`/api/v1/${path}`,{...init,headers:{"Content-Type":"application/json",...init?.headers}});
    const data=await response.json(); if(!response.ok) throw new Error(data?.error?.message??`Request failed (${response.status})`); return data;
  },[]);
  async function generate(){if(!scenario)return; setBusy(true);setError("");try{setPlan(await call(`scenarios/${encodeURIComponent(scenario.id)}/rescue-plans`,{method:"POST"}));}catch(e){setError(e instanceof Error?e.message:"Could not generate plan.");}finally{setBusy(false);}}
  async function decide(action:"approved"|"rejected"){if(!plan)return;setBusy(true);setError("");try{setPlan(await call(`rescue-plans/${plan.plan_id}/decision`,{method:"POST",body:JSON.stringify({action,expected_version:plan.scenario_version,reason:action==="rejected"?"Commander rejected from Command Center":"Commander approval"})}));}catch(e){setError(e instanceof Error?e.message:"Decision failed.");}finally{setBusy(false);}}
  async function saveAssignments(){if(!plan)return;setBusy(true);setError("");try{const assignments=plan.missions.map((m,i)=>assignmentKeys[i]??`${m.unit_id}|${m.destination_id}`).map(key=>{const [unit_id,destination_id]=key.split("|");return {unit_id,destination_id};});setPlan(await call(`rescue-plans/${plan.plan_id}/assignments`,{method:"PATCH",body:JSON.stringify({expected_version:plan.scenario_version,assignments})}));}catch(e){setError(e instanceof Error?e.message:"Assignment edit failed.");}finally{setBusy(false);}}
  async function closeRoad(){if(!scenario||!road)return;setBusy(true);setError("");try{await call(`scenarios/${encodeURIComponent(scenario.id)}/road-closures`,{method:"POST",body:JSON.stringify({road_id:road,reason:"Command Center manual closure"})});setPlan(await call(`scenarios/${encodeURIComponent(scenario.id)}/rescue-plans`,{method:"POST"}));}catch(e){setPlan(null);setError(e instanceof Error?e.message:"Could not close road or regenerate the recommendation.");}finally{setBusy(false);}}
  useEffect(()=>{
    if(!scenario||!plan||plan.status!=="proposed"||plan.scenario_id!==scenario.id||plan.scenario_version===scenario.state_version)return;
    let active=true;setBusy(true);setError("");
    call(`scenarios/${encodeURIComponent(scenario.id)}/rescue-plans`,{method:"POST"}).then(value=>{if(active)setPlan(value as Plan);}).catch(e=>{if(active)setError(e instanceof Error?e.message:"Could not refresh the stale proposal.");}).finally(()=>{if(active)setBusy(false);});
    return()=>{active=false;};
  },[scenario,plan,setPlan,call]);
  useEffect(()=>{
    if(!scenarioId)return;let live=true;let seq=0;
    const refresh=async()=>{const requestId=++seq;try{const found=await fetchLatestRecommendation(scenarioId);if(!live||requestId!==seq)return;const current=planRef.current;if(found&&(!current||current.plan_id!==found.plan_id||current.status!==found.status))setPlan(found as unknown as Plan);else if(!found&&current?.status==="proposed"&&current.scenario_id===scenarioId)setPlan(null);}catch{/* The command workspace remains usable if the local recommendation endpoint is temporarily unavailable. */}};
    void refresh();const timer=window.setInterval(()=>void refresh(),2500);return()=>{live=false;window.clearInterval(timer)};
  },[scenarioId,setPlan]);
  return <Panel title="Rescue planning" eyebrow="COMMANDER REVIEW" action={<Badge>{plan?.status??"No proposal"}</Badge>}>
    <p className="muted">Plans are scenario-versioned recommendations. Boat routing is unsupported until water access and docking are modeled.</p>
    {scenario&&<p className="mono">Scenario v{scenario.state_version} · Tick {scenario.tick}</p>}
    <div className="rescue-actions"><button className="primary-button" disabled={!scenario||busy} onClick={generate}>{busy?"Working…":"Generate recommendation"}</button></div>
    {error&&<p role="alert" className="rescue-error">{error}</p>}
    {plan&&<>
      {plan.scenario_version!==scenario?.state_version&&plan.status==="proposed"&&<p role="alert" className="rescue-error">Stale proposal: the simulation changed. Generate a new plan.</p>}
      <p className="muted">Plan v{plan.scenario_version} · Tick {plan.simulation_tick} · {plan.solver_status}</p>
      <div className="rescue-metrics"><span>Covered <b>{plan.comparison.optimized.destinations_covered}</b></span><span>Distance <b>{plan.comparison.optimized.total_distance_m} m</b></span><span>Baseline <b>{plan.comparison.baseline.destinations_covered}</b></span></div>
      <h3>Ranked destinations</h3>{plan.priorities.slice(0,5).map(d=><div className="rescue-row" key={d.building_id}><b>{d.name}</b><Badge>{d.priority_score.toFixed(1)}</Badge><small>{d.explanation}</small></div>)}
      <h3>Recommended missions</h3>{plan.missions.map((m,index)=><div className="rescue-row" key={`${m.unit_id}-${index}`}><b>{m.unit_id} → {city.buildings.find(b=>b.id===m.destination_id)?.name??m.destination_id}</b>{plan.status==="proposed"&&<select aria-label={`Edit mission ${index+1}`} value={assignmentKeys[index]??`${m.unit_id}|${m.destination_id}`} onChange={e=>setAssignmentKeys(current=>({...current,[index]:e.target.value}))}>{plan.available_assignments.map(option=><option key={`${option.unit_id}|${option.destination_id}`} value={`${option.unit_id}|${option.destination_id}`}>{option.unit_id} → {city.buildings.find(b=>b.id===option.destination_id)?.name??option.destination_id}</option>)}</select>}<small>Capacity {m.unit_capacity} · targets up to {m.occupants_targeted} occupants · {m.route.distance_m} m · {m.route.simulated_minutes} synthetic minutes · {m.route.road_ids.join(", ")}</small></div>)}
      {!!plan.unreachable.length&&<details className="rescue-unreachable"><summary>{plan.unreachable.length} destinations have no supported route in this scenario</summary><p className="muted">No mission is created for these destinations. A route is supported only when the synthetic road graph has a permitted connection under current flood depths, closures, bridge status, and unit limits.</p><ul>{plan.unreachable.slice(0,5).map(item=><li key={item.building_id}><b>{city.buildings.find(building=>building.id===item.building_id)?.name??item.building_id}</b>: {item.reason}</li>)}</ul>{plan.unreachable.length>5&&<small>{plan.unreachable.length-5} additional destinations omitted from this summary.</small>}</details>}
      {plan.status==="proposed"&&plan.scenario_version===scenario?.state_version&&<div className="rescue-actions"><button className="secondary-button" disabled={busy} onClick={saveAssignments}>Save assignment edits</button><button className="primary-button" disabled={busy} onClick={()=>decide("approved")}>Approve plan</button><button className="secondary-button" disabled={busy} onClick={()=>decide("rejected")}>Reject</button></div>}
      <small>Recommendations require commander approval. Approval reserves assigned units. Arrived or completed missions keep their units reserved until a commander explicitly returns each unit to service; a scenario reset starts a new resource epoch.</small>
    </>}
    <h3>Manual road closure</h3><div className="rescue-actions"><select aria-label="Road to close" value={road} onChange={e=>setRoad(e.target.value)}>{city.roads.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select><button className="secondary-button" disabled={!scenario||busy} onClick={closeRoad}>Close road & invalidate proposals</button></div>
  </Panel>;
}
