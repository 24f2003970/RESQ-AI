import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Activity, AlertTriangle, Check, Clock3, Focus, LoaderCircle, MapPinned, Pause, Play, Radio, Route, Truck } from "lucide-react";
import {
  advanceMissionClock, approveMissionRoute, controlMissionClock, fetchAgentDashboard, fetchMissionClock,
  fetchMissionEvents, fetchMissionUnits, fetchMissions, missionCommand, requestMissionRoute,
  type CityState, type Mission, type MissionClock, type MissionEvent, type MissionUnitResource,
  type ScenarioState,
} from "../api/client";
import { Badge, Panel } from "./ui";

type Snapshot = { scenarioId:string|null; scenarioEpoch:number|null; missions: Mission[]; units: MissionUnitResource[]; clock: MissionClock | null };
const statusLabel: Record<Mission["status"],string> = {
  ready:"Ready · reserved", en_route:"En route", blocked:"Blocked · review needed",
  arrived:"Arrived · awaiting confirmation", completed:"Completed · fictional simulation", cancelled:"Cancelled",
};
const statusTone: Record<Mission["status"],"green"|"amber"|"red"|undefined> = {
  ready:"amber",en_route:"green",blocked:"red",arrived:"green",completed:undefined,cancelled:undefined,
};
function proposalRevision(mission:Mission):string|null {
  const proposal=mission.route_proposal;
  return proposal&&typeof proposal==="object"&&"route_revision_id" in proposal&&typeof proposal.route_revision_id==="string"?proposal.route_revision_id:null;
}
function routeRoads(mission:Mission):string[] {
  const roads=mission.route.road_ids;
  return Array.isArray(roads)?roads.filter((road):road is string=>typeof road==="string"):[];
}
function time(seconds:number){return `${Math.floor(seconds/60)}m ${String(seconds%60).padStart(2,"0")}s`;}

export default function MissionOperations({
  scenario,city,onSnapshot,onSelectMission,selectedMissionId,
}: {
  scenario:ScenarioState|null;city:CityState;
  onSnapshot:(snapshot:Snapshot)=>void;
  onSelectMission:(missionId:string|null)=>void;
  selectedMissionId:string|null;
}) {
  const [missions,setMissions]=useState<Mission[]>([]);
  const [units,setUnits]=useState<MissionUnitResource[]>([]);
  const [clock,setClock]=useState<MissionClock|null>(null);
  const [events,setEvents]=useState<MissionEvent[]>([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const [agentTrace,setAgentTrace]=useState("");
  const sequence=useRef(0);
  const snapshotIdentity=useRef("");
  const [loadedScenarioIdentity,setLoadedScenarioIdentity]=useState("");
  const mutationInFlight=useRef(false);
  const selectedMissionRef=useRef(selectedMissionId);
  selectedMissionRef.current=selectedMissionId;
  const activeScenario=scenario?.id;
  const activeEpoch=scenario?.epoch;
  const activeIdentity=activeScenario&&activeEpoch!==undefined?JSON.stringify([activeScenario,activeEpoch]):"";
  const identityRef=useRef(activeIdentity);
  identityRef.current=activeIdentity;
  const dataIsCurrent=Boolean(activeIdentity)&&loadedScenarioIdentity===activeIdentity;
  const visibleMissions=useMemo(()=>dataIsCurrent?missions:[],[dataIsCurrent,missions]);
  const visibleUnits=dataIsCurrent?units:[];
  const visibleClock=dataIsCurrent?clock:null;
  const selected=useMemo(()=>visibleMissions.find(item=>item.mission_id===selectedMissionId)??null,[visibleMissions,selectedMissionId]);
  const refresh=useCallback(async(signal?:AbortSignal)=>{
    if(!activeScenario||activeEpoch===undefined||mutationInFlight.current)return;
    const id=++sequence.current;
    const [nextMissions,nextClock,nextUnits]=await Promise.all([
      fetchMissions(activeScenario,signal,activeEpoch),fetchMissionClock(activeScenario,signal),fetchMissionUnits(activeScenario,signal),
    ]);
    if(id!==sequence.current||signal?.aborted||identityRef.current!==JSON.stringify([activeScenario,activeEpoch]))return;
    if(nextMissions.some(item=>item.scenario_id!==activeScenario||item.scenario_epoch!==activeEpoch)||nextClock.scenario_id!==activeScenario||nextClock.scenario_epoch!==activeEpoch||nextUnits.some(item=>item.scenario_id!==activeScenario||item.scenario_epoch!==activeEpoch))return;
    const identity=JSON.stringify([nextMissions,nextClock,nextUnits]);
    if(identity!==snapshotIdentity.current){
      snapshotIdentity.current=identity;
      setLoadedScenarioIdentity(JSON.stringify([activeScenario,activeEpoch]));
      setMissions(nextMissions);setClock(nextClock);setUnits(nextUnits);
      onSnapshot({scenarioId:activeScenario,scenarioEpoch:activeEpoch,missions:nextMissions,units:nextUnits,clock:nextClock});
    }
    const currentSelection=selectedMissionRef.current;
    if(!currentSelection||!nextMissions.some(item=>item.mission_id===currentSelection)){
      const nextSelection=nextMissions[0]?.mission_id??null;
      if(nextSelection!==currentSelection){selectedMissionRef.current=nextSelection;onSelectMission(nextSelection);}
    }
  },[activeScenario,activeEpoch,onSnapshot,onSelectMission]);
  useEffect(()=>{
    snapshotIdentity.current="";
    setLoadedScenarioIdentity("");
    if(!activeScenario||activeEpoch===undefined){setMissions([]);setUnits([]);setClock(null);setEvents([]);selectedMissionRef.current=null;onSelectMission(null);onSnapshot({scenarioId:null,scenarioEpoch:null,missions:[],units:[],clock:null});return;}
    setMissions([]);setUnits([]);setClock(null);setEvents([]);
    selectedMissionRef.current=null;onSelectMission(null);
    onSnapshot({scenarioId:activeScenario,scenarioEpoch:activeEpoch,missions:[],units:[],clock:null});
    const controller=new AbortController();
    refresh(controller.signal).catch(cause=>{if(!controller.signal.aborted)setError(cause instanceof Error?cause.message:"Mission service is unavailable.");});
    const timer=window.setInterval(()=>refresh(controller.signal).catch(cause=>{if(!controller.signal.aborted)setError(cause instanceof Error?cause.message:"Mission service is unavailable.");}),1500);
    return()=>{controller.abort();window.clearInterval(timer);sequence.current+=1;};
  },[activeScenario,activeEpoch,refresh,onSnapshot,onSelectMission]);
  useEffect(()=>{
    if(!selectedMissionId){setEvents([]);return;}
    let live=true;let requestNumber=0;
    const load=()=>{const n=++requestNumber;fetchMissionEvents(selectedMissionId).then(value=>{if(live&&n===requestNumber)setEvents(value);}).catch(()=>{if(live)setEvents([]);});};
    load();const timer=window.setInterval(load,2000);
    return()=>{live=false;window.clearInterval(timer);};
  },[selectedMissionId]);
  useEffect(()=>{
    if(!activeScenario||activeEpoch===undefined){setAgentTrace("");return;}
    setAgentTrace("");
    let live=true;let sequenceId=0;
    const load=()=>{const current=++sequenceId;fetchAgentDashboard(activeScenario).then(dashboard=>{
      if(live&&current===sequenceId&&identityRef.current===JSON.stringify([activeScenario,activeEpoch])&&dashboard.scenario_epoch===activeEpoch)setAgentTrace(dashboard.latest_trace?.summary??"");
    }).catch(()=>{});};
    load();const timer=window.setInterval(load,4000);
    return()=>{live=false;window.clearInterval(timer);};
  },[activeScenario,activeEpoch]);

  function applyMutationResult(result:unknown){
    if(!result||typeof result!=="object")return;
    if("clock" in result&&"missions" in result&&Array.isArray(result.missions)){
      const advance=result as {clock:MissionClock;missions:Mission[]};
      if(advance.clock.scenario_id!==activeScenario||advance.clock.scenario_epoch!==activeEpoch)return;
      setClock(advance.clock);
      setMissions(previous=>{const merged=new Map(previous.map(item=>[item.mission_id,item]));for(const item of advance.missions)merged.set(item.mission_id,item);return [...merged.values()];});
      setLoadedScenarioIdentity(activeIdentity);
      return;
    }
    if("mission_id" in result){
      const updated=result as Mission;
      if(updated.scenario_id!==activeScenario||updated.scenario_epoch!==activeEpoch)return;
      setMissions(previous=>{const index=previous.findIndex(item=>item.mission_id===updated.mission_id);if(index<0)return [...previous,updated];const next=[...previous];next[index]=updated;return next;});
      setLoadedScenarioIdentity(activeIdentity);
      return;
    }
    if("scenario_id" in result&&"scenario_epoch" in result&&"seconds" in result){
      const updated=result as MissionClock;
      if(updated.scenario_id===activeScenario&&updated.scenario_epoch===activeEpoch){setClock(updated);setLoadedScenarioIdentity(activeIdentity);}
    }
  }
  async function run(action:()=>Promise<unknown>,success:string){
    if(mutationInFlight.current)return;
    setBusy(true);setError("");setMessage("");
    mutationInFlight.current=true;
    const mutationGeneration=++sequence.current;
    try{
      const result=await action();
      if(identityRef.current!==activeIdentity)throw new Error("Scenario epoch changed while the operation was saving. Refresh the active scenario before continuing.");
      applyMutationResult(result);
      if(mutationGeneration!==sequence.current)throw new Error("A newer mission update superseded this operation; synchronizing current state.");
      setMessage(success);
    }
    catch(cause){setError(cause instanceof Error?cause.message:"The mission command could not be completed.");}
    finally{mutationInFlight.current=false;setBusy(false);void refresh().catch(cause=>setError(cause instanceof Error?cause.message:"Mission state synchronization is pending."));}
  }
  const selectedUnit=selected?visibleUnits.find(unit=>unit.unit_id===selected.unit_id):null;
  const destination=selected?city.buildings.find(building=>building.id===selected.destination_id):null;
  const revisionId=selected?proposalRevision(selected):null;
  const hasMoving=visibleMissions.some(item=>item.status==="en_route");

  return <Panel title="Mission Operations" eyebrow="FICTIONAL LOCAL SIMULATION" action={<Radio size={16}/> }>
    <div className="mission-truth"><AlertTriangle size={14}/><span>Simulation only. No real responders are contacted or dispatched.</span></div>
    {!scenario&&<p className="muted">Choose a saved scenario to inspect its mission records.</p>}
    {error&&!selected&&<p className="mission-feedback error" role="alert"><AlertTriangle size={14}/>{error}</p>}
    {scenario&&visibleMissions.length===0&&<div className="mission-empty"><Truck size={20}/><div><b>No approved missions in this epoch</b><span>Approve a rescue plan to create reserved, ready missions. Approval does not dispatch a vehicle.</span></div></div>}
    {visibleMissions.length>0&&<div className="mission-list" role="list" aria-label="Scenario missions">
      {visibleMissions.map(mission=><button className={`mission-row ${selectedMissionId===mission.mission_id?"selected":""}`} key={mission.mission_id} onClick={()=>onSelectMission(mission.mission_id)} aria-pressed={selectedMissionId===mission.mission_id}>
        <span className={`mission-status-dot ${mission.status}`}/><span className="mission-row-main"><b>{mission.unit_id}<i>→</i>{city.buildings.find(building=>building.id===mission.destination_id)?.name??mission.destination_id}</b><small>{mission.mission_id.slice(0,22)} · {statusLabel[mission.status]}</small></span><Badge tone={statusTone[mission.status]}>{mission.status.replaceAll("_"," ")}</Badge>
      </button>)}
    </div>}
    {selected&&<div className="mission-detail">
      <div className="mission-detail-head"><div><span className="eyebrow">SELECTED MISSION</span><strong>{selected.unit_id} <span>→</span> {destination?.name??selected.destination_id}</strong></div><button className="mission-focus" title="Focus selected unit in the Digital Twin" aria-label="Focus selected mission vehicle" onClick={()=>onSelectMission(selected.mission_id)}><Focus size={15}/></button></div>
      <div className="mission-facts">
        <span><small>STATUS</small><b>{statusLabel[selected.status]}</b></span>
        <span><small>TRAVELLED</small><b>{selected.traversed_distance_m.toFixed(1)} m</b></span>
        <span><small>REMAINING</small><b>{selected.remaining_distance_m.toFixed(1)} m</b></span>
        <span><small>SYNTHETIC ETA</small><b>{time(selected.estimated_remaining_seconds)}</b></span>
        <span><small>OPS CLOCK</small><b>{visibleClock?time(visibleClock.seconds):"—"}{visibleClock?.paused?" · paused":""}</b></span>
        <span><small>CAPACITY / TARGET</small><b>{selected.unit_capacity} / {selected.occupants_targeted} <i>synthetic planning values</i></b></span>
      </div>
      <div className="mission-route-summary"><Route size={14}/><span>{selected.route_revision>1?`Approved route revision ${selected.route_revision}`:"Approved route"} · segment {selected.route_segment_index+1} · {routeRoads(selected).length?routeRoads(selected).join(" → "):"access spur only"}</span></div>
      {selected.block_reason&&<div className="mission-block-alert" role="alert"><AlertTriangle size={15}/><span>{selected.block_reason}</span></div>}
      {selected.route_proposal&&<div className="mission-route-review"><b>Replacement route awaits commander approval</b><span>{routeRoads({...selected,route:(selected.route_proposal.route as Record<string,unknown>)??selected.route}).join(" → ")||"Alternative path calculated"}</span></div>}
      <div className="mission-controls">
        {selected.status==="ready"&&<button className="primary-button" disabled={busy} onClick={()=>void run(()=>missionCommand(selected.mission_id,"dispatch",selected.mission_version),"Dispatch authorized; the unit will move only when mission time advances.")}><Play size={14}/> Dispatch mission</button>}
        {hasMoving&&visibleClock&&<button className="secondary-button" disabled={busy} onClick={()=>void run(()=>controlMissionClock(scenario!.id,visibleClock,visibleClock.paused?"resume":"pause"),visibleClock.paused?"Mission clock resumed.":"Mission clock paused.")}>{visibleClock.paused?<Play size={14}/>:<Pause size={14}/>} {visibleClock.paused?"Resume clock":"Pause clock"}</button>}
        {hasMoving&&visibleClock&&!visibleClock.paused&&<button className="secondary-button" disabled={busy} onClick={()=>void run(()=>advanceMissionClock(scenario!.id,visibleClock,scenario!.state_version,10),"Mission clock advance confirmed by the backend.")}><Clock3 size={14}/> Advance 10 seconds</button>}
        {selected.status==="blocked"&&!selected.route_proposal&&<button className="primary-button" disabled={busy} onClick={()=>void run(()=>requestMissionRoute(selected.mission_id,selected.mission_version),"Routing Agent path calculation saved for commander review.")}><MapPinned size={14}/> Calculate replacement route</button>}
        {selected.status==="blocked"&&revisionId&&<button className="primary-button" disabled={busy} onClick={()=>void run(()=>approveMissionRoute(selected.mission_id,selected.mission_version,revisionId),"Replacement route approved; mission may continue on the next clock advance.")}><Check size={14}/> Approve route revision</button>}
        {selected.status==="arrived"&&<button className="primary-button" disabled={busy} onClick={()=>void run(()=>missionCommand(selected.mission_id,"complete",selected.mission_version),"Simulated mission completion recorded; no rescue outcome is asserted.")}><Check size={14}/> Confirm simulated completion</button>}
        {["ready","en_route","blocked","arrived"].includes(selected.status)&&<button className="secondary-button mission-cancel" disabled={busy} onClick={()=>{const reason=window.prompt("Reason for cancelling this fictional mission?");if(reason?.trim())void run(()=>missionCommand(selected.mission_id,"cancel",selected.mission_version,reason.trim()),selected.status==="ready"?"Ready mission cancelled; reservation released.":"Mission cancelled; unit stays unavailable at its recorded position until restored.");}}><AlertTriangle size={14}/> Cancel mission</button>}
        {selected.status==="completed"&&selectedUnit?.status==="unavailable"&&<button className="secondary-button" disabled={busy} onClick={()=>void run(()=>missionCommand(selected.mission_id,"restore",selected.mission_version),"Unit returned to service at its recorded location; no return trip is simulated.")}><Truck size={14}/> Return unit to service</button>}
        {selected.status==="cancelled"&&selectedUnit?.status==="unavailable"&&<button className="secondary-button" disabled={busy} onClick={()=>void run(()=>missionCommand(selected.mission_id,"restore",selected.mission_version),"Unit restored at its recorded location; no return trip is simulated.")}><Truck size={14}/> Restore unit from current location</button>}
      </div>
      {busy&&<p className="mission-feedback" role="status"><LoaderCircle className="spin" size={14}/> Saving local operation…</p>}
      {message&&<p className="mission-feedback success" role="status"><Check size={14}/>{message}</p>}
      {error&&<p className="mission-feedback error" role="alert"><AlertTriangle size={14}/>{error}</p>}
      <div className="mission-timeline"><div className="mission-timeline-head"><b><Activity size={13}/> Persisted event history</b><span>{selected.plan_id.slice(0,18)} · plan</span></div>
        {events.slice(-4).reverse().map(event=><div className="mission-event" key={event.event_id}><i/><span><b>{event.event_type.replaceAll("_"," ")}</b><small>Ops +{time(event.clock_seconds)} · v{event.mission_version}</small></span></div>)}
        {!events.length&&<small className="muted">No mission events recorded yet.</small>}
      </div>
      {agentTrace&&<div className="mission-agent-trace"><b><Activity size={13}/> Latest persisted agent trace</b><p>{agentTrace}</p><span>Agent recommendations remain advisory. Commander controls govern mission changes.</span></div>}
    </div>}
    {scenario&&visibleClock&&<div className="mission-clock-footer"><span><Clock3 size={13}/> Operational clock · {time(visibleClock.seconds)} · v{visibleClock.version}</span><small>Independent from the five-minute flood simulation clock</small></div>}
    <p className="mission-synthetic-note">Targeted occupants are synthetic planning values. Arrival and completion do not verify evacuation or lives saved.</p>
    {busy&&<span className="sr-only"><LoaderCircle/></span>}
  </Panel>;
}
