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
});
