import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Activity, AlertTriangle, ArrowRight, RefreshCw, RotateCcw } from "lucide-react";
import { fetchAgentDashboard, fetchAgentEvents, fetchAgentTrace, requestIntelligenceAssessment, retryAgentEvent, type AgentDashboard, type AgentEventEnvelope, type AgentTraceDetail, type ScenarioState } from "../api/client";
import { Badge, Panel } from "./ui";

const LABELS: Record<string,string> = {hazard_intelligence:"Hazard Intelligence",impact_assessment:"Impact Assessment",rescue_priority:"Rescue Priority",routing:"Routing",resource_allocation:"Resource Allocation",commander_strategy:"Commander / Strategy"};
const tone=(status:string)=>status==="completed"?"green":status==="degraded"||status==="superseded"?"amber":status==="failed"?"red":"";
const pretty=(value:string)=>value.replaceAll("_"," ");

export function AgentCommandPanel({scenarioId}:{scenarioId:string|null}) {
  const [dashboard,setDashboard]=useState<AgentDashboard|null>(null);
  useEffect(()=>{if(!scenarioId)return;let live=true;let seq=0;const refresh=()=>{const n=++seq;fetchAgentDashboard(scenarioId).then(v=>{if(live&&n===seq)setDashboard(v)}).catch(()=>{});};refresh();const timer=window.setInterval(refresh,3000);return()=>{live=false;window.clearInterval(timer)}},[scenarioId]);
  if(!scenarioId)return null;
  const trace=dashboard?.latest_trace;
  const roadChanges=trace?.evidence?.road_changes;
  const routeRun=dashboard?.latest_runs.find(run=>run.agent_name==="routing"&&run.event_id===trace?.event_id);
  const allocationRun=dashboard?.latest_runs.find(run=>run.agent_name==="resource_allocation"&&run.event_id===trace?.event_id);
  const accessChanged=Array.isArray(roadChanges)&&roadChanges.length>0&&["completed","degraded"].includes(routeRun?.status??"")&&["completed","degraded"].includes(allocationRun?.status??"");
  return <Panel title="AI coordination" eyebrow="EVENT-DRIVEN RESPONSE" action={<Badge tone={dashboard?.pending_events?"amber":"green"}>{dashboard?.pending_events?`${dashboard.pending_events} processing`:"Local agents"}</Badge>}>
    {dashboard? <>
      <p className="agent-command-summary">{accessChanged?"Road or bridge access changed. Routing and allocation were reassessed.":trace?.summary??"No decision trace has been recorded for this scenario yet."}</p>
      <div className="agent-command-metrics"><span>{dashboard.available_ground_units} ground units available</span><span>{dashboard.reserved_ground_units?.length??0} reserved</span><span>{dashboard.latest_runs.filter(r=>r.status==="failed").length} agent failures</span></div>
      {dashboard.approved_route_review_required&&<Link className="agent-review-alert" to={`/decisions?event=${encodeURIComponent(trace?.event_id??"")}`}><AlertTriangle size={16}/> An approved route intersects blocked infrastructure · commander review required <ArrowRight size={15}/></Link>}
      {dashboard.commander_action_required&&!dashboard.approved_route_review_required&&<Link className="agent-review-alert" to={`/decisions?event=${encodeURIComponent(trace?.event_id??"")}`}><AlertTriangle size={16}/> Commander review required · proposal ready <ArrowRight size={15}/></Link>}
      {trace&&!dashboard.commander_action_required&&<Link className="agent-trace-link" to={`/decisions?event=${encodeURIComponent(trace.event_id)}`}>Inspect latest decision trace <ArrowRight size={14}/></Link>}
      <div className="agent-mini-flow">{dashboard.definitions.map((agent)=><span key={agent.name} title={`${agent.title}: ${dashboard.latest_runs.find(r=>r.agent_name===agent.name)?.status??"waiting"}`}><i className={dashboard.latest_runs.find(r=>r.agent_name===agent.name)?.status??"waiting"}/>{agent.position}</span>)}</div>
    </>:<p className="muted">Connecting to local agent status…</p>}
  </Panel>;
}

export default function AgentExplorer({scenario}:{scenario:ScenarioState|null}) {
  const [search,setSearch]=useSearchParams();
  const [dashboard,setDashboard]=useState<AgentDashboard|null>(null);
  const [events,setEvents]=useState<AgentEventEnvelope[]>([]);
  const [detail,setDetail]=useState<AgentTraceDetail|null>(null);
  const [selectedAgent,setSelectedAgent]=useState("");
  const [loading,setLoading]=useState(true);const [error,setError]=useState("");const [busy,setBusy]=useState(false);
  const refreshSequence=useRef(0);
  const selectedEventId=search.get("event");
  const refresh=useCallback(async(signal?:AbortSignal)=>{
    if(!scenario)return;
    const sequence=++refreshSequence.current;
    try{const [d,e]=await Promise.all([fetchAgentDashboard(scenario.id,signal),fetchAgentEvents(scenario.id,signal)]);if(sequence===refreshSequence.current&&!signal?.aborted){setDashboard(d);setEvents(e);setError("");}}
    catch(err){if(sequence===refreshSequence.current&&!signal?.aborted)setError(err instanceof Error?err.message:"The local agent service is unavailable.");}
    finally{if(sequence===refreshSequence.current&&!signal?.aborted)setLoading(false)}
  },[scenario]);
  useEffect(()=>{const controller=new AbortController();void refresh(controller.signal);const timer=window.setInterval(()=>void refresh(controller.signal),2500);return()=>{controller.abort();window.clearInterval(timer)}},[refresh]);
  useEffect(()=>{if(!scenario)return;const id=selectedEventId??events[0]?.event_id;if(!id){setDetail(null);return}let live=true;fetchAgentTrace(id).then(v=>{if(live)setDetail(v)}).catch(err=>{if(live&&selectedEventId)setError(err instanceof Error?err.message:"Could not load the decision trace.")});return()=>{live=false}},[scenario,selectedEventId,events]);
  const selectedRun=useMemo(()=>detail?.agents.find(a=>a.agent_name===selectedAgent)??detail?.agents[0]??null,[detail,selectedAgent]);
  const relatedPlan=detail?.related_plan as {status:string;missions:{unit_id:string;destination_id:string;route:{road_ids:string[]}}[]}|null|undefined;
  async function assess(){if(!scenario)return;setBusy(true);try{const receipt=await requestIntelligenceAssessment(scenario.id);setSearch({event:receipt.event_id});await refresh()}catch(err){setError(err instanceof Error?err.message:"Could not queue assessment.")}finally{setBusy(false)}}
  async function retry(){if(!detail)return;setBusy(true);try{await retryAgentEvent(detail.event.event_id);await refresh()}catch(err){setError(err instanceof Error?err.message:"Could not retry event.")}finally{setBusy(false)}}
  const historic=!!detail&&!!scenario&&detail.event.scenario_epoch!==scenario.epoch;
  const stale=!!detail&&!!scenario&&(detail.event.simulation_state_version!==scenario.state_version||detail.event.infrastructure_revision!==dashboard?.infrastructure_revision);
  return <main className="agent-explorer">
    <header className="agent-hero"><div><span className="eyebrow">SIX ALGORITHMIC AGENTS · PERSISTED EVENT EVIDENCE</span><h1>AI Decision Explorer</h1><p>Follow real scenario events through six algorithmic agents. Each recommendation stays a proposal until the commander decides.</p></div><button className="primary-button" disabled={!scenario||busy} onClick={assess}><Activity size={16}/>{busy?"Working…":"Run assessment"}</button></header>
    {error&&<div className="agent-error" role="alert"><AlertTriangle size={17}/>{error}<button className="secondary-button small" onClick={()=>void refresh()}><RefreshCw size={14}/> Retry connection</button></div>}
    {!scenario&&<Panel title="Scenario unavailable"><p>Connect to the local service to inspect agent activity.</p></Panel>}
    {scenario&&<>
      <div className="agent-context"><span>{scenario.name}</span><span>Epoch {scenario.epoch} · Tick {scenario.tick} · Version {scenario.state_version}</span><span>Infrastructure rev {dashboard?.infrastructure_revision??"—"}</span><span className="mono">Simulation time is separate from processing time</span></div>
      {historic&&<div className="agent-warning"><AlertTriangle size={17}/>Historical trace from epoch {detail.event.scenario_epoch}; current scenario is epoch {scenario.epoch}. Historical recommendations cannot be applied.</div>}
      {stale&&!historic&&<div className="agent-warning"><AlertTriangle size={17}/>This trace was generated against an older scenario or infrastructure revision. Its proposal requires a fresh assessment.</div>}
      <div className="agent-explorer-grid">
        <div className="agent-left-column">
          <Panel title="Agent activity" eyebrow="PERSISTED RUNS" action={<Badge tone={dashboard?.pending_events?"amber":"green"}>{dashboard?.pending_events?"Processing":"Connected"}</Badge>}>
            {loading&&!dashboard?<p className="muted">Loading saved agent runs…</p>:<div className="agent-cards">{(dashboard?.definitions??[]).map(def=>{const run=dashboard?.latest_runs.find(item=>item.agent_name===def.name);return <button key={def.name} className={`agent-card ${selectedAgent===def.name?"selected":""}`} onClick={()=>{setSelectedAgent(def.name);if(run)setSearch({event:run.event_id})}}><span className="agent-card-top"><b>{def.title}</b><Badge tone={tone(run?.status??"waiting")}>{pretty(run?.status??"waiting")}</Badge></span><small>{def.responsibility}</small><span className="agent-card-foot">{run?`v${run.simulation_state_version} · ${run.duration_ms??"—"} ms`:"No execution recorded"}</span></button>})}</div>}
          </Panel>
          <Panel title="Decision timeline" eyebrow="EVENTS & OUTCOMES">
            {events.length?<div className="agent-timeline">{events.map(event=><button key={event.event_id} className={`agent-timeline-item ${detail?.event.event_id===event.event_id?"selected":""}`} onClick={()=>setSearch({event:event.event_id})}><i/><div><b>{pretty(event.event_type)}</b><small>Tick {event.simulation_tick} · v{event.simulation_state_version} · {event.affected_entity_ids?.length??0} affected IDs</small><small>{new Date(event.created_at_utc).toLocaleString()}</small></div><Badge>{event.event_id.slice(0,8)}</Badge></button>)}</div>:<p className="muted">{loading?"Loading events…":"No agent events yet. Advance or adjust a scenario, or run an assessment."}</p>}
          </Panel>
        </div>
        <div className="agent-right-column">
          <Panel title="Decision inspector" eyebrow={detail?`EVENT ${detail.event.event_id.slice(0,10)}`:"SELECT AN EVENT"} action={detail&&<Badge tone={tone(detail.event_status)}>{pretty(detail.event_status)}</Badge>}>
            {detail?<>
              <p className="agent-summary">{detail.trace?.summary??(typeof detail.event.payload?.reason==="string"?detail.event.payload.reason:"Processing has not produced a decision trace yet.")}</p>
              <div className="agent-evidence-grid"><span>Scenario version<b>{detail.event.simulation_state_version}</b></span><span>Infrastructure revision<b>{detail.event.infrastructure_revision??"n/a"}</b></span><span>Processing attempts<b>{detail.attempts}</b></span><span>Correlation<b>{detail.event.correlation_id.slice(0,12)}</b></span></div>
              {selectedRun&&<div className="agent-run-inspector"><div className="agent-inspector-title"><h3>{LABELS[selectedRun.agent_name]??selectedRun.agent_name}</h3><Badge tone={tone(selectedRun.status)}>{pretty(selectedRun.status)}</Badge></div><p>{selectedRun.explanation}</p>{selectedRun.error&&<p className="agent-error-text">{selectedRun.error}</p>}<h4>Numerical evidence</h4><pre>{JSON.stringify(selectedRun.numerical_evidence,null,2)}</pre><h4>Output summary</h4><pre>{JSON.stringify(selectedRun.output_summary,null,2)}</pre></div>}
              {detail.trace?.evidence&&<div className="agent-route-delta"><b>Infrastructure & route changes</b><small>Road changes: {Array.isArray(detail.trace.evidence.road_changes)?(detail.trace.evidence.road_changes as string[]).join(", ")||"none":"none"}</small><small>Changed route pairs: {Array.isArray(detail.trace.evidence.route_changes)?(detail.trace.evidence.route_changes as string[]).join(", ")||"none":"none"}</small><small>Invalidated route pairs: {Array.isArray(detail.trace.evidence.invalidated_routes)?(detail.trace.evidence.invalidated_routes as string[]).join(", ")||"none":"none"}</small><small>Active manual closures: {Array.isArray(detail.trace.evidence.manual_closures)?(detail.trace.evidence.manual_closures as string[]).join(", ")||"none":"none"}</small></div>}
              {relatedPlan&&<div className="agent-related-plan"><h3>Recommendation</h3><Badge tone={relatedPlan.status==="proposed"?"amber":""}>{pretty(relatedPlan.status)}</Badge>{relatedPlan.missions.length?relatedPlan.missions.map((m,index)=><Link className="agent-mission-link" key={`${m.unit_id}-${index}`} to={`/?review=latest&destination=${encodeURIComponent(m.destination_id)}`}><span>{m.unit_id} → {m.destination_id}</span><small>{m.route.road_ids.join(", ")}</small><ArrowRight size={13}/></Link>):<p>No assigned missions</p>}{relatedPlan.status==="proposed"&&<Link className="agent-trace-link" to="/?review=latest">Open Command Center review <ArrowRight size={14}/></Link>}</div>}
              {detail.event_status==="failed"&&<button className="secondary-button" disabled={busy||detail.attempts>=3} onClick={retry}><RotateCcw size={14}/> Retry event</button>}
              {detail.trace&&<details className="agent-trace-evidence"><summary>Full trace evidence</summary><pre>{JSON.stringify(detail.trace.evidence,null,2)}</pre></details>}
            </>:<p className="muted">Select a persisted event to inspect its trigger, agent evidence, route outcomes and proposal.</p>}
          </Panel>
          <Panel title="Coordination flow" eyebrow="EXECUTION ORDER">
            <div className="agent-flow">{(dashboard?.definitions??[]).map((agent,index)=>{const run=detail?.agents.find(a=>a.agent_name===agent.name);return <div key={agent.name} className="agent-flow-node"><span className={`agent-flow-state ${run?.status??"waiting"}`}>{index+1}</span><div><b>{agent.title}</b><small>{run?pretty(run.status):"waiting for selected event"}</small></div>{index<5&&<i/>}</div>})}</div>
          </Panel>
        </div>
      </div>
    </>}
  </main>;
}
