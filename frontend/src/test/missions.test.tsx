import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useCallback, useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import cityFixture from "./fixtures/city.json";
import scenarioFixture from "./fixtures/scenario.json";
import MissionOperations from "../components/MissionOperations";
import type { Mission, MissionClock, MissionUnitResource } from "../api/client";

const api=vi.hoisted(()=>({
  advanceMissionClock:vi.fn(),approveMissionRoute:vi.fn(),controlMissionClock:vi.fn(),fetchAgentDashboard:vi.fn(),
  fetchMissionClock:vi.fn(),fetchMissionEvents:vi.fn(),fetchMissionUnits:vi.fn(),fetchMissions:vi.fn(),missionCommand:vi.fn(),requestMissionRoute:vi.fn(),
}));
vi.mock("../api/client",()=>api);

const city=cityFixture as never as import("../api/client").CityState;
const scenario=scenarioFixture.state as import("../api/client").ScenarioState;
const mission:Mission={
  mission_id:"mission-test-001",plan_id:"plan-test-001",scenario_id:scenario.id,scenario_epoch:scenario.epoch,
  simulation_version:scenario.state_version,infrastructure_revision:0,mission_version:1,unit_id:"unit-1",unit_type:"ambulance",
  destination_id:"building-hospital",unit_capacity:2,occupants_targeted:2,status:"ready",
  route:{reachable:true,road_ids:["road-ns-0"],edge_ids:["road-ns-0:segment:0-1"],polyline:[[0,0],[20,0]],
    segment_lengths_m:[20],segment_speeds_mps:[5],polyline_xyz:[[0,0,0],[20,0,0]]},route_revision:1,
  traversed_distance_m:0,total_distance_m:20,remaining_distance_m:20,route_segment_index:0,
  position:{x_m:0,y_m:0,elevation_m:0},operational_seconds:0,estimated_remaining_seconds:4,
  dispatch_clock_seconds:null,arrival_clock_seconds:null,completion_clock_seconds:null,block_reason:null,route_proposal:null,
  created_at:"2026-10-01T00:00:00Z",updated_at:"2026-10-01T00:00:00Z",
};
const clock:MissionClock={scenario_id:scenario.id,scenario_epoch:scenario.epoch,seconds:0,version:1,paused:false};
const unit:MissionUnitResource={scenario_id:scenario.id,scenario_epoch:scenario.epoch,unit_id:"unit-1",status:"reserved",mission_id:mission.mission_id,position:{x_m:0,y_m:0,elevation_m:0},version:1,updated_at:"2026-10-01T00:00:00Z"};
const onSnapshot=vi.fn();const onSelectMission=vi.fn();

function setup(records:Mission[]=[mission],offline=false){
  api.fetchMissions.mockResolvedValue(records);api.fetchMissionClock.mockResolvedValue(clock);
  api.fetchMissionUnits.mockResolvedValue([unit]);api.fetchMissionEvents.mockResolvedValue([]);
  api.fetchAgentDashboard.mockResolvedValue({latest_trace:null});
  if(offline)api.fetchMissions.mockRejectedValue(new Error("Local service offline."));
  function ControlledPanel(){
    const [selectedMissionId,setSelectedMissionId]=useState<string|null>(null);
    const select=useCallback((id:string|null)=>{onSelectMission(id);setSelectedMissionId(id);},[]);
    return <MissionOperations city={city} scenario={scenario} onSnapshot={onSnapshot} onSelectMission={select} selectedMissionId={selectedMissionId}/>;
  }
  return render(<ControlledPanel/>);
}
function deferred<T>(){let resolve!:(value:T)=>void;let reject!:(reason?:unknown)=>void;const promise=new Promise<T>((yes,no)=>{resolve=yes;reject=no;});return{promise,resolve,reject};}

describe("Mission Operations panel",()=>{
  beforeEach(()=>{vi.clearAllMocks();});

  it("loads persisted missions and calls the explicit dispatch API",async()=>{
    setup();
    expect(await screen.findByText("Ready · reserved")).toBeTruthy();
    expect(screen.getByText("20.0 m")).toBeTruthy();
    fireEvent.click(screen.getByRole("button",{name:/Dispatch mission/i}));
    await waitFor(()=>expect(api.missionCommand).toHaveBeenCalledWith(mission.mission_id,"dispatch",mission.mission_version));
  });

  it("shows blocked route review and requests a route proposal from the backend",async()=>{
    const blocked={...mission,status:"blocked" as const,mission_version:4,block_reason:"Road road-ns-0 closed ahead."};
    setup([blocked]);
    expect(await screen.findByText("Blocked · review needed")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("closed ahead");
    fireEvent.click(screen.getByRole("button",{name:/Calculate replacement route/i}));
    await waitFor(()=>expect(api.requestMissionRoute).toHaveBeenCalledWith(blocked.mission_id,blocked.mission_version));
  });

  it("requires explicit completion after arrival",async()=>{
    const arrived={...mission,status:"arrived" as const,mission_version:7,traversed_distance_m:20,remaining_distance_m:0};
    setup([arrived]);
    fireEvent.click(await screen.findByRole("button",{name:/Confirm simulated completion/i}));
    await waitFor(()=>expect(api.missionCommand).toHaveBeenCalledWith(arrived.mission_id,"complete",arrived.mission_version));
  });

  it("shows a clear error when the local service is unavailable",async()=>{
    setup([],true);
    expect(await screen.findByRole("alert")).toHaveTextContent("Local service offline.");
  });

  it("clears the old selected mission when switching to an epoch with no missions",async()=>{
    api.fetchMissions.mockImplementation(async(scenarioId:string)=>scenarioId===scenario.id?[mission]:[]);
    api.fetchMissionClock.mockResolvedValue(clock);
    api.fetchMissionUnits.mockResolvedValue([unit]);
    api.fetchMissionEvents.mockResolvedValue([]);
    api.fetchAgentDashboard.mockResolvedValue({latest_trace:null});
    function ScenarioSwitcher(){
      const [activeScenario,setActiveScenario]=useState(scenario);
      const [selectedMissionId,setSelectedMissionId]=useState<string|null>(null);
      const [,setSnapshot]=useState<unknown>(null);
      const acceptSnapshot=useCallback((value:unknown)=>setSnapshot(value),[]);
      return <>
        <button onClick={()=>{setSelectedMissionId(mission.mission_id);setActiveScenario({...scenario,id:"scenario-next-epoch"});}}>Switch scenario with prior selection</button>
        <output aria-label="Parent mission selection">{selectedMissionId??"none"}</output>
        <MissionOperations city={city} scenario={activeScenario} onSnapshot={acceptSnapshot} onSelectMission={setSelectedMissionId} selectedMissionId={selectedMissionId}/>
      </>;
    }
    render(<ScenarioSwitcher/>);
    fireEvent.click(await screen.findByRole("button",{name:"Switch scenario with prior selection"}));
    await waitFor(()=>expect(screen.getByLabelText("Parent mission selection")).toHaveTextContent("none"));
    await waitFor(()=>expect(screen.getByText("No approved missions in this epoch")).toBeInTheDocument());
    expect(screen.queryByRole("button",{name:/mission-test-001/i})).not.toBeInTheDocument();
  });

  it("applies the authoritative clock advance response to the visible time, distance, position and mission status",async()=>{
    const moving={...mission,status:"en_route" as const,mission_version:2,dispatch_clock_seconds:0};
    const movingClock={...clock,seconds:20,version:3};
    api.fetchMissions.mockResolvedValue([moving]);api.fetchMissionClock.mockResolvedValue(movingClock);api.fetchMissionUnits.mockResolvedValue([{...unit,status:"en_route"}]);
    api.fetchMissionEvents.mockResolvedValue([]);api.fetchAgentDashboard.mockResolvedValue({latest_trace:null});
    const advanced={...moving,status:"arrived" as const,mission_version:3,traversed_distance_m:20,remaining_distance_m:0,route_segment_index:1,position:{x_m:20,y_m:0,elevation_m:0}};
    api.advanceMissionClock.mockResolvedValue({clock:{...movingClock,seconds:30,version:4},missions:[advanced],infrastructure_revision:0});
    function Selected(){const [selectedId,setSelectedId]=useState<string|null>(moving.mission_id);return <MissionOperations city={city} scenario={scenario} onSnapshot={onSnapshot} onSelectMission={setSelectedId} selectedMissionId={selectedId}/>;}
    render(<Selected/>);
    expect(await screen.findByText("20.0 m")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button",{name:/Advance 10 seconds/i}));
    expect(await screen.findByText("0.0 m")).toBeInTheDocument();
    expect(screen.getByText("0m 30s")).toBeInTheDocument();
    expect(screen.getByText("Arrived · awaiting confirmation")).toBeInTheDocument();
    expect(screen.getByText(/Mission clock advance confirmed by the backend/)).toBeInTheDocument();
    expect(screen.getByText(/segment 2/)).toBeInTheDocument();
  });

  it("keeps a newer acknowledged advance when an older polling response arrives afterward",async()=>{
    const moving={...mission,status:"en_route" as const,mission_version:2};
    const stalePoll=deferred<Mission[]>();let missionReads=0;
    api.fetchMissions.mockImplementation(()=>{missionReads++;return missionReads===2?stalePoll.promise:Promise.resolve([moving]);});
    api.fetchMissionClock.mockResolvedValue({...clock,seconds:20,version:3});api.fetchMissionUnits.mockResolvedValue([{...unit,status:"en_route"}]);
    api.fetchMissionEvents.mockResolvedValue([]);api.fetchAgentDashboard.mockResolvedValue({latest_trace:null});
    const advanced={...moving,mission_version:4,traversed_distance_m:10,total_distance_m:20,remaining_distance_m:10,position:{x_m:10,y_m:0,elevation_m:0}};
    api.advanceMissionClock.mockResolvedValue({clock:{...clock,seconds:30,version:4},missions:[advanced],infrastructure_revision:0});
    function Selected(){const [selectedId,setSelectedId]=useState<string|null>(moving.mission_id);return <MissionOperations city={city} scenario={scenario} onSnapshot={onSnapshot} onSelectMission={setSelectedId} selectedMissionId={selectedId}/>;}
    render(<Selected/>);
    expect(await screen.findByText("0.0 m")).toBeInTheDocument();
    await waitFor(()=>expect(missionReads).toBeGreaterThanOrEqual(2),{timeout:3000});
    fireEvent.click(screen.getByRole("button",{name:/Advance 10 seconds/i}));
    expect((await screen.findAllByText("10.0 m")).length).toBeGreaterThan(0);
    expect(screen.getByText("0m 30s")).toBeInTheDocument();
    stalePoll.resolve([moving]);
    await new Promise(resolve=>setTimeout(resolve,0));
    expect(screen.getAllByText("10.0 m").length).toBeGreaterThan(0);
    expect(screen.getByText("0m 30s")).toBeInTheDocument();
  });

  it("coalesces repeated clock advance clicks while one request is still in flight",async()=>{
    const moving={...mission,status:"en_route" as const,mission_version:2};
    api.fetchMissions.mockResolvedValue([moving]);api.fetchMissionClock.mockResolvedValue({...clock,seconds:20,version:3});api.fetchMissionUnits.mockResolvedValue([{...unit,status:"en_route"}]);
    api.fetchMissionEvents.mockResolvedValue([]);api.fetchAgentDashboard.mockResolvedValue({latest_trace:null});
    const pending=deferred<{clock:MissionClock;missions:Mission[];infrastructure_revision:number}>();api.advanceMissionClock.mockReturnValue(pending.promise);
    function Selected(){const [selectedId,setSelectedId]=useState<string|null>(moving.mission_id);return <MissionOperations city={city} scenario={scenario} onSnapshot={onSnapshot} onSelectMission={setSelectedId} selectedMissionId={selectedId}/>;}
    render(<Selected/>);
    const button=await screen.findByRole("button",{name:/Advance 10 seconds/i});
    fireEvent.click(button);fireEvent.click(button);
    await waitFor(()=>expect(api.advanceMissionClock).toHaveBeenCalledTimes(1));
    pending.resolve({clock:{...clock,seconds:30,version:4},missions:[{...moving,mission_version:3,traversed_distance_m:10,remaining_distance_m:10,position:{x_m:10,y_m:0,elevation_m:0}}],infrastructure_revision:0});
    expect((await screen.findAllByText("10.0 m")).length).toBeGreaterThan(0);
  });

  it("ignores a delayed previous-epoch poll after a same-ID epoch reset and clears selected route data",async()=>{
    const moving={...mission,status:"en_route" as const,mission_version:8};
    const oldMissions=deferred<Mission[]>();
    api.fetchMissions.mockImplementation((...args)=>args[2]===scenario.epoch?oldMissions.promise:Promise.resolve([]));
    api.fetchMissionClock.mockImplementation(async()=>({...clock,scenario_epoch:activeEpochValue}));
    api.fetchMissionUnits.mockImplementation(async()=>activeEpochValue===scenario.epoch?[{...unit,status:"en_route"}]:[]);
    api.fetchMissionEvents.mockResolvedValue([]);api.fetchAgentDashboard.mockImplementation(async()=>({scenario_epoch:activeEpochValue,latest_trace:null}));
    let activeEpochValue=scenario.epoch;
    function EpochSwitcher(){
      const [activeScenario,setActiveScenario]=useState(scenario);
      const [selectedMissionId,setSelectedMissionId]=useState<string|null>(moving.mission_id);
      const [snapshot,setSnapshot]=useState<unknown>(null);
      const accept=useCallback((value:unknown)=>setSnapshot(value),[]);
      return <><button onClick={()=>{activeEpochValue=scenario.epoch+1;setActiveScenario({...scenario,epoch:activeEpochValue});}}>Reset same scenario epoch</button><output aria-label="Parent selection">{selectedMissionId??"none"}</output><output aria-label="Parent snapshot">{JSON.stringify(snapshot)}</output><MissionOperations city={city} scenario={activeScenario} onSnapshot={accept} onSelectMission={setSelectedMissionId} selectedMissionId={selectedMissionId}/></>;
    }
    render(<EpochSwitcher/>);
    await waitFor(()=>expect(api.fetchMissions).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button",{name:"Reset same scenario epoch"}));
    await waitFor(()=>expect(screen.getByText("No approved missions in this epoch")).toBeInTheDocument());
    expect(screen.getByLabelText("Parent selection")).toHaveTextContent("none");
    expect(screen.getByLabelText("Parent snapshot")).not.toHaveTextContent(moving.mission_id);
    oldMissions.resolve([moving]);
    await waitFor(()=>expect(screen.getByText("No approved missions in this epoch")).toBeInTheDocument());
    expect(screen.queryByText(/Backend mission route/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button",{name:/Dispatch mission/i})).not.toBeInTheDocument();
  });

  it("does not report success when an advance is rejected for a stale expected version",async()=>{
    const moving={...mission,status:"en_route" as const,mission_version:2};
    api.fetchMissions.mockResolvedValue([moving]);api.fetchMissionClock.mockResolvedValue({...clock,seconds:20,version:3});api.fetchMissionUnits.mockResolvedValue([{...unit,status:"en_route"}]);
    api.fetchMissionEvents.mockResolvedValue([]);api.fetchAgentDashboard.mockResolvedValue({latest_trace:null});
    api.advanceMissionClock.mockRejectedValue(new Error("Mission clock version is stale; refresh before advancing."));
    function Selected(){const [selectedId,setSelectedId]=useState<string|null>(moving.mission_id);return <MissionOperations city={city} scenario={scenario} onSnapshot={onSnapshot} onSelectMission={setSelectedId} selectedMissionId={selectedId}/>;}
    render(<Selected/>);
    fireEvent.click(await screen.findByRole("button",{name:/Advance 10 seconds/i}));
    expect(await screen.findByRole("alert")).toHaveTextContent("Mission clock version is stale");
    expect(screen.queryByText(/advance confirmed/i)).not.toBeInTheDocument();
  });

  it("renders an authoritative en-route to blocked transition with its route review action",async()=>{
    const moving={...mission,status:"en_route" as const,mission_version:2};
    api.fetchMissions.mockResolvedValue([moving]);api.fetchMissionClock.mockResolvedValue({...clock,seconds:20,version:3});api.fetchMissionUnits.mockResolvedValue([{...unit,status:"en_route"}]);
    api.fetchMissionEvents.mockResolvedValue([]);api.fetchAgentDashboard.mockResolvedValue({latest_trace:null});
    const blocked={...moving,status:"blocked" as const,mission_version:3,traversed_distance_m:10,remaining_distance_m:10,block_reason:"Road road-ns-0 closed ahead."};
    api.advanceMissionClock.mockResolvedValue({clock:{...clock,seconds:30,version:4},missions:[blocked],infrastructure_revision:1});
    function Selected(){const [selectedId,setSelectedId]=useState<string|null>(moving.mission_id);return <MissionOperations city={city} scenario={scenario} onSnapshot={onSnapshot} onSelectMission={setSelectedId} selectedMissionId={selectedId}/>;}
    render(<Selected/>);
    expect(await screen.findByRole("button",{name:/Advance 10 seconds/i})).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button",{name:/Advance 10 seconds/i}));
    expect(await screen.findByText("Blocked · review needed")).toBeInTheDocument();
    expect(screen.getAllByText("10.0 m").length).toBeGreaterThan(0);
    expect(screen.getByRole("alert")).toHaveTextContent("Road road-ns-0 closed ahead.");
    expect(screen.getByRole("button",{name:/Calculate replacement route/i})).toBeInTheDocument();
    expect(screen.queryByRole("button",{name:/Advance 10 seconds/i})).not.toBeInTheDocument();
  });

  it("does not produce a maximum-update-depth warning while identical polls synchronize parent state",async()=>{
    const consoleError=vi.spyOn(console,"error").mockImplementation(()=>{});
    api.fetchMissions.mockResolvedValue([mission]);api.fetchMissionClock.mockResolvedValue(clock);api.fetchMissionUnits.mockResolvedValue([unit]);
    api.fetchMissionEvents.mockResolvedValue([]);api.fetchAgentDashboard.mockResolvedValue({latest_trace:null});
    const view=setup();
    expect(await screen.findByText("Ready · reserved")).toBeInTheDocument();
    await new Promise(resolve=>setTimeout(resolve,1600));
    const depthWarnings=consoleError.mock.calls.flat().filter(value=>String(value).includes("Maximum update depth exceeded"));
    expect(depthWarnings).toHaveLength(0);
    view.unmount();consoleError.mockRestore();
  });
});
