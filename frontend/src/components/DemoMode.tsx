import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, ArrowLeft, ArrowRight, Check, CircleDot, LoaderCircle, RotateCcw, ShieldCheck, Waves } from "lucide-react";
import {
  advanceScenario, closeScenarioRoad, createScenario, createScenarioExperiment,
  decideRescuePlan, fetchAgentDashboard, fetchAgentEvents, fetchAgentTrace,
  fetchLatestRecommendation, fetchMLModel, fetchScenarioPredictions,
  fetchScenarioExperiment, requestIntelligenceAssessment, resetScenario,
  updateScenarioParameters,
  type AgentTraceDetail, type RescueRecommendation, type ScenarioEnvelope,
  type ScenarioExperiment, type ScenarioState,
} from "../api/client";
import { Badge, Panel } from "./ui";

const STAGES=[
  {title:"Initial city",intro:"Introduce the seeded fictional city, facilities and response inventory."},
  {title:"Flood event",intro:"Apply the reproducible severe forcing and advance the existing flood simulator."},
  {title:"AI risk intelligence",intro:"Read current physical exposure and the locally trained future-risk estimates as separate outputs."},
  {title:"Agent coordination",intro:"Queue a real assessment event and wait for the persisted six-agent pipeline."},
  {title:"Rescue recommendation",intro:"Inspect the current commander-review proposal, assigned units and graph routes."},
  {title:"Infrastructure disruption",intro:"Close an open road used by a current planned route through the backend API."},
  {title:"Autonomous replanning",intro:"Wait for the closure-triggered run and verify that the affected route changed or became unreachable."},
  {title:"Human decision",intro:"The commander can approve or reject the fresh proposal. Nothing is auto-approved."},
  {title:"Impact comparison",intro:"Run an isolated same-snapshot resource comparison and inspect real baseline/optimized metrics."},
  {title:"Explainability",intro:"Open the persisted event trace that records the closure and agent calculations."},
];
type ClosureEvidence={roadId:string;unitId:string;destinationId:string;beforeRoads:string[];beforePlanId:string;afterPlanId?:string;afterRoads?:string[];becameUnreachable?:boolean;eventId?:string};

function delay(ms:number){return new Promise(resolve=>window.setTimeout(resolve,ms))}
function missions(plan:RescueRecommendation){return plan.missions as Array<{unit_id:string;destination_id:string;route:{road_ids:string[]}}>}
function freshRoads(plan:RescueRecommendation,unitId:string,destinationId:string){
  const assignments=plan.available_assignments as Array<{unit_id:string;destination_id:string;route:{road_ids:string[]}}>;
  return assignments.find(item=>item.unit_id===unitId&&item.destination_id===destinationId)?.route.road_ids??null;
}

export default function DemoMode({scenario,onChange}:{scenario:ScenarioState|null;onChange:(envelope:ScenarioEnvelope)=>void}){
  const navigate=useNavigate();
  const [demo,setDemo]=useState<ScenarioState|null>(null);const active=demo??scenario;
  const [stage,setStage]=useState(0);const [busy,setBusy]=useState(false);const [error,setError]=useState("");const [message,setMessage]=useState("");
  const [modelStatus,setModelStatus]=useState<{status:string;message:string;predicted:number;physical:number}|null>(null);
  const [assessmentEventId,setAssessmentEventId]=useState("");const [currentPlan,setCurrentPlan]=useState<RescueRecommendation|null>(null);
  const [closure,setClosure]=useState<ClosureEvidence|null>(null);const [trace,setTrace]=useState<AgentTraceDetail|null>(null);
  const [comparison,setComparison]=useState<ScenarioExperiment|null>(null);const [decision,setDecision]=useState("");
  const progress=useMemo(()=>STAGES.map((_,index)=>index<stage?"complete":index===stage?"current":"upcoming"),[stage]);
  async function run(action:()=>Promise<void>){if(busy)return;setBusy(true);setError("");setMessage("");try{await action()}catch(reason){setError(reason instanceof Error?reason.message:"The guided demo action failed. Check the local service and retry this stage.")}finally{setBusy(false)}}
  async function updateScenario(next:ScenarioEnvelope){setDemo(next.state);onChange(next)}

  async function initialize(){
    const envelope=await createScenario("RESQ-AI Guided Demo · Seed 2026","mild");
    await updateScenario(envelope);setStage(1);setCurrentPlan(null);setClosure(null);setTrace(null);setComparison(null);setDecision("");
    setMessage("Created a new isolated operational scenario from seed 2026. Existing scenarios remain unchanged.");
  }
  async function flood(){
    if(!active)throw new Error("Create the demo scenario first.");
    const changed=await updateScenarioParameters(active,{rainfall_mm_h:90,river_level_m:1.4,drainage_effectiveness:0.2});
    const flooded=await advanceScenario(changed.state,12,true);await updateScenario(flooded);setStage(2);
    setMessage(`${flooded.state.simulated_seconds/60} simulated minutes · ${flooded.state.affected_buildings} physically exposed buildings · ${flooded.state.exposed_roads} exposed roads. These counts are from the backend flood state.`);
  }
  async function assessRisk(){
    if(!active)throw new Error("The guided scenario is missing.");
    const [model,predictions]=await Promise.all([fetchMLModel(),fetchScenarioPredictions(active)]);
    const predicted=predictions.predictions.filter(item=>item.predicted_future_exposed).length;
    const physical=active.affected_buildings;
    setModelStatus({status:model.status,message:model.status==="ready"?`${model.model_name} · ${model.horizon_minutes??"—"} minute synthetic label horizon. Scores are uncalibrated.`:model.unavailable_reason??"The local model artifact is unavailable.",predicted,physical});
    if(model.status!=="ready")throw new Error("The demo requires local ML inference. The local service reports the model unavailable; install/train the project artifact, then retry this stage.");
    setStage(3);setMessage(`${physical} currently physically exposed buildings; ${predicted} model predictions labeled future-exposed. These are different measurements.`);
  }
  async function coordinate(){
    if(!active)throw new Error("The guided scenario is missing.");
    const receipt=await requestIntelligenceAssessment(active.id);setAssessmentEventId(receipt.event_id);
    const deadline=Date.now()+90_000;let latest:AgentTraceDetail|undefined;
    while(Date.now()<deadline){latest=await fetchAgentTrace(receipt.event_id);setTrace(latest);if(["completed","degraded","failed","superseded"].includes(latest.event_status))break;await delay(600)}
    if(!latest||!["completed","degraded"].includes(latest.event_status))throw new Error(latest?.event_status==="failed"?"The agent pipeline failed. Open its trace, correct the reported issue, and retry.":"Timed out waiting for the real agent event. No completion is assumed.");
    setStage(4);setMessage(`Event ${receipt.event_id.slice(0,12)} finished with ${latest.event_status}; ${latest.agents.length} ordered agent records are persisted.`);
  }
  async function inspectRecommendation(){
    if(!active)throw new Error("The guided scenario is missing.");
    const plan=await fetchLatestRecommendation(active.id);
    if(!plan)throw new Error("No fresh commander-review proposal exists yet. Re-run the assessment stage and inspect the Decision Explorer.");
    if(!missions(plan).length)throw new Error("The strategy agent produced no feasible mission assignment. Inspect the persisted trace before choosing another scenario.");
    setCurrentPlan(plan);setStage(5);setMessage(`${missions(plan).length} destinations assigned in proposal ${plan.plan_id.slice(0,12)}. Approval is still required.`);
  }
  async function disruptRoad(){
    if(!active||!currentPlan)throw new Error("Inspect the current recommendation first.");
    const candidate=missions(currentPlan).find(item=>item.route.road_ids.length>0);
    if(!candidate)throw new Error("The proposal has no graph route with a closable road segment.");
    const roadId=candidate.route.road_ids[0];
    await closeScenarioRoad(active.id,roadId,"Guided demo: close an edge on the current planned rescue route.");
    setClosure({roadId,unitId:candidate.unit_id,destinationId:candidate.destination_id,beforeRoads:candidate.route.road_ids,beforePlanId:currentPlan.plan_id});
    const events=await fetchAgentEvents(active.id);const event=events.find(item=>item.event_type==="infrastructure_changed"&&item.payload?.road_id===roadId&&item.payload?.action==="close");
    if(event){setClosure(value=>value?{...value,eventId:event.event_id}:value);setAssessmentEventId(event.event_id)}
    setStage(6);setMessage(`Closed ${roadId}, which is on ${candidate.unit_id}’s saved route to ${candidate.destination_id}. Waiting for the infrastructure-change trigger.`);
  }
  async function waitForReplan(){
    if(!active||!closure)throw new Error("Close a road on a current proposal route first.");
    const deadline=Date.now()+90_000;let nextPlan:RescueRecommendation|null=null;let eventId=closure.eventId??"";let latestTrace:AgentTraceDetail|undefined;
    while(Date.now()<deadline){
      const events=await fetchAgentEvents(active.id);const event=events.find(item=>item.event_type==="infrastructure_changed"&&item.payload?.road_id===closure.roadId&&item.payload?.action==="close");
      if(event){eventId=event.event_id;latestTrace=await fetchAgentTrace(eventId);setTrace(latestTrace);}
      nextPlan=await fetchLatestRecommendation(active.id);
      if(latestTrace&&["completed","degraded"].includes(latestTrace.event_status)&&nextPlan&&nextPlan.plan_id!==closure.beforePlanId)break;
      await delay(600);
    }
    if(!latestTrace||!["completed","degraded"].includes(latestTrace.event_status))throw new Error("The closure-triggered agent event did not complete in time; no replan will be claimed.");
    if(!nextPlan)throw new Error("The closure pipeline completed but produced no fresh proposal. Review the trace for its infeasibility explanation.");
    const afterRoads=freshRoads(nextPlan,closure.unitId,closure.destinationId);
    const changed=afterRoads===null||JSON.stringify(afterRoads)!==JSON.stringify(closure.beforeRoads);
    if(!changed)throw new Error(`The agent pipeline completed, but ${closure.unitId} → ${closure.destinationId} kept the same route. The demo will not claim a route change; reset and try a different route edge.`);
    setCurrentPlan(nextPlan);setClosure({...closure,eventId,afterPlanId:nextPlan.plan_id,afterRoads:afterRoads??undefined,becameUnreachable:afterRoads===null});setAssessmentEventId(eventId);setStage(7);
    setMessage(afterRoads===null?`${closure.unitId} → ${closure.destinationId} is now unreachable under the closed-road graph.`:`Route changed from ${closure.beforeRoads.join(" → ")} to ${afterRoads.join(" → ")}. Fresh proposal ${nextPlan.plan_id.slice(0,12)} is ready for human review.`);
  }
  async function review(action:"approved"|"rejected"){
    if(!active||!currentPlan)throw new Error("A fresh proposal is required for commander review.");
    const result=await decideRescuePlan(currentPlan.plan_id,action,active.state_version,action==="rejected"?"Rejected in the guided hackathon demo after review.":"Approved by the human commander in the guided demo.");
    setCurrentPlan(result);setDecision(result.status);setStage(8);setMessage(`Human commander ${result.status} proposal ${result.plan_id.slice(0,12)}. No automated approval occurred.`);
  }
  async function compareImpact(){
    if(!active||!closure)throw new Error("Complete infrastructure disruption and re-planning first.");
    const body={name:"Guided demo · resource availability",base_scenario_id:active.id,expected_state_version:active.state_version,simulation_ticks:0,variants:[
      {variant_id:"A" as const,label:"Four ground units",available_ambulances:2,available_ground_teams:2,closed_road_ids:[closure.roadId]},
      {variant_id:"B" as const,label:"Two ground units",available_ambulances:1,available_ground_teams:1,closed_road_ids:[closure.roadId]},
    ]};
    let record=await createScenarioExperiment(active.id,body);setComparison(record);
    const deadline=Date.now()+90_000;
    while(Date.now()<deadline&&["pending","running","cancel_requested"].includes(record.status)){await delay(500);record=await fetchScenarioExperiment(record.experiment_id);setComparison(record)}
    if(record.status!=="completed")throw new Error(record.error??"The isolated impact comparison did not complete.");
    setStage(9);setMessage(`Saved experiment ${record.experiment_id.slice(0,12)} completed. Its comparison uses an exact snapshot and does not reserve operational resources.`);
  }
  async function explain(){
    const eventId=closure?.eventId??assessmentEventId;
    if(!eventId)throw new Error("No persisted event trace is available yet.");
    navigate(`/decisions?event=${encodeURIComponent(eventId)}`);
  }
  async function restart(){
    if(!active) {setStage(0);return}
    const dashboard=await fetchAgentDashboard(active.id);
    if((dashboard.reserved_ground_units?.length??0)>0&&!window.confirm("This scenario has approved rescue plans reserving units. Reset starts a new epoch and makes those approvals historical; no mission completion is simulated. Reset the demo scenario?"))return;
    const envelope=await resetScenario(active);await updateScenario(envelope);setStage(0);setCurrentPlan(null);setClosure(null);setTrace(null);setComparison(null);setDecision("");setAssessmentEventId("");setModelStatus(null);setMessage("Demo scenario returned to its initial seeded conditions. Prior traces remain historical.");
  }
  const actions=[initialize,flood,assessRisk,coordinate,inspectRecommendation,disruptRoad,waitForReplan,()=>review("approved"),compareImpact,explain];
  const actionLabels=["Initialize demo scenario","Apply severe flood · advance 12 ticks","Run local model inference","Run six-agent assessment","Load rescue proposal","Close route-relevant road","Wait for verified replan","Review and decide","Run isolated A/B impact comparison","Open persisted decision trace"];
  return <main className="demo-page">
    <header className="demo-hero"><div><span className="eyebrow">GUIDED HACKATHON DEMONSTRATION · SEED 2026</span><h1>From flood to response</h1><p>A repeatable walk through the actual simulator, local model, persisted agents, route graph and commander review.</p></div><button className="secondary-button" onClick={()=>void run(restart)} disabled={busy}><RotateCcw size={15}/> Reset demo</button></header>
    <div className="demo-truth-banner"><ShieldCheck size={17}/><span>Backend-computed evidence only. Flood conditions, ML future-risk estimates and agent recommendations are separate outputs. The city and labels are synthetic.</span></div>
    <div className="demo-grid"><nav className="demo-stage-nav" aria-label="Guided demo stages">{STAGES.map((item,index)=><button key={item.title} className={`demo-stage ${progress[index]}`} onClick={()=>{if(index<=stage)setStage(index)}} disabled={busy||index>stage}><span>{index<stage?<Check size={14}/>:index+1}</span><div><b>{item.title}</b><small>{item.intro}</small></div></button>)}</nav>
      <section className="demo-stage-content"><Panel title={`Stage ${stage+1} · ${STAGES[stage].title}`} eyebrow={`DEMO PROGRESS · ${stage+1} OF ${STAGES.length}`} action={<Badge tone={busy?"amber":stage===9?"green":""}>{busy?"Running":stage===9?"Ready to repeat":"Human-guided"}</Badge>}>
        <p className="demo-stage-intro">{STAGES[stage].intro}</p>
        <div className="demo-context-grid"><span>Scenario<strong>{active?.name??"Not initialized"}</strong></span><span>Seed<strong>{active?.seed??"—"}</strong></span><span>Simulation tick<strong>{active?.tick??"—"}</strong></span><span>Physical exposure<strong>{active?`${active.affected_buildings} buildings`:"—"}</strong></span></div>
        {stage===0&&<div className="demo-evidence"><p>The generated city contains hospitals, a shelter, roads, bridges and rescue units. The scenario will be created as a separate local record using seed 2026.</p></div>}
        {stage===2&&modelStatus&&<div className="demo-evidence"><b>Local future-risk model · {modelStatus.status}</b><p>{modelStatus.message}</p><div className="demo-context-grid"><span>Current physical exposure<strong>{modelStatus.physical} buildings</strong></span><span>Predicted future exposure<strong>{modelStatus.predicted} buildings</strong></span></div><p>Future-risk labels use a synthetic training set and uncalibrated scores; they are not operational forecasts.</p></div>}
        {stage===3&&trace&&<div className="demo-evidence"><b>Persisted assessment · {trace.event_status}</b><p>Event {assessmentEventId}</p><div className="demo-agent-timeline">{trace.agents.map(run=><span key={run.run_id}><i className={run.status}/><b>{run.agent_name}</b><small>{run.status} · {run.duration_ms??"—"} ms</small></span>)}</div></div>}
        {(stage===4||stage===5)&&currentPlan&&<div className="demo-evidence"><b>Proposal {currentPlan.plan_id} · {currentPlan.status}</b><p>{currentPlan.explanation}</p>{missions(currentPlan).map(mission=><div className="demo-mission" key={`${mission.unit_id}-${mission.destination_id}`}><span>{mission.unit_id} → {mission.destination_id}</span><small>Route segments: {mission.route.road_ids.join(" · ")}</small></div>)}</div>}
        {(stage===6||stage===7)&&closure&&<div className="demo-evidence"><b>Road closure · {closure.roadId}</b><p>Original assignment: {closure.unitId} → {closure.destinationId}</p><p>Original road sequence: {closure.beforeRoads.join(" → ")}</p>{closure.afterRoads&&<p>Replanned road sequence: {closure.afterRoads.join(" → ")}</p>}{closure.becameUnreachable&&<p>The destination became unreachable for the original unit under the new graph.</p>}{closure.eventId&&<p>Infrastructure event: <code>{closure.eventId}</code></p>}</div>}
        {stage===7&&currentPlan?.status==="proposed"&&<div className="demo-human-review"><p>Human decision required. Review the route and trace before choosing.</p><button className="primary-button" disabled={busy} onClick={()=>void run(()=>review("approved"))}>Approve proposal</button><button className="secondary-button" disabled={busy} onClick={()=>void run(()=>review("rejected"))}>Reject proposal</button></div>}
        {stage===7&&decision&&<div className="demo-evidence"><b>Commander decision · {decision}</b><p>The recorded plan status is {decision}. This decision was made through the approval API.</p></div>}
        {stage===8&&comparison?.status==="completed"&&<div className="demo-evidence"><b>Saved experiment {comparison.experiment_id}</b><p>{(comparison.results as unknown as {comparison:{fairness:string}}).comparison.fairness}</p><p>Variant A and B outputs, baseline/optimized metrics, time series and timings are persisted for the Scenario Lab.</p></div>}
        {trace&&stage===9&&<div className="demo-evidence"><b>Decision trace · {trace.event_status}</b><p>{trace.trace?.summary??"Agent run evidence is saved for this event."}</p><p>Trigger event: <code>{trace.event.event_id}</code></p></div>}
        {message&&<div className="demo-message" role="status"><CircleDot size={15}/>{message}</div>}{error&&<div className="demo-error" role="alert"><AlertTriangle size={16}/>{error}</div>}
        {stage!==7&&<div className="demo-action-row"><button className="primary-button" disabled={busy||(!active&&stage>0)} onClick={()=>void run(actions[stage])}>{busy?<><LoaderCircle className="spin" size={15}/> Working…</>:<>{stage===0?<Waves size={15}/>:<ArrowRight size={15}/>} {actionLabels[stage]}</>}</button>{stage>0&&<button className="secondary-button" disabled={busy} onClick={()=>setStage(value=>Math.max(0,value-1))}><ArrowLeft size={15}/> Previous stage</button>}</div>}
        {stage===9&&<div className="demo-action-row"><button className="secondary-button" disabled={busy} onClick={()=>void run(restart)}><RotateCcw size={15}/> Reset and run again</button></div>}
      </Panel>
      {active&&<p className="scenario-note">Active scenario is a separate record. Approved reservations last until an epoch reset; the system does not simulate mission completion or automatic resource release.</p>}
      {comparison?.status==="failed"&&<div className="demo-error" role="alert">Comparison failed: {comparison.error}</div>}
    </section></div>
  </main>;
}
