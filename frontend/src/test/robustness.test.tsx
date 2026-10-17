import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import city from "./fixtures/city.json";
import scenario from "./fixtures/scenario.json";
import RobustnessLab from "../components/RobustnessLab";
import RobustnessSummary from "../components/RobustnessSummary";
import type { CityState, ScenarioState } from "../api/client";

vi.mock("../scene/CityScene",()=>({default:()=> <div data-testid="hypothetical-scene"/>}));

const baseline={scenario_id:"scenario-demo",scenario_epoch:2,simulation_state_version:15,infrastructure_revision:4,simulation_tick:9,seed:2026,available_unit_ids:["unit-a","unit-b"],reserved_unit_ids:["unit-c"],manual_closure_road_ids:[],plans:[{plan_id:"plan-demo",status:"proposed",assignment_count:1,solver_status:"optimal_linear_sum_assignment"}],model_reliability:{status:"available",warnings:[],calibration_status:"validated_synthetic",probabilities_calibrated:true}};
const mission={unit_id:"unit-a",destination_id:"building-1",route:{polyline:[[0,0],[10,0]],distance_m:10,simulated_minutes:1}};
const completed={study_id:"study-demo",scenario_id:"scenario-demo",scenario_epoch:2,simulation_state_version:15,infrastructure_revision:4,simulation_tick:9,seed:2026,original_plan_id:"plan-demo",snapshot_sha256:"a".repeat(64),frozen_available_unit_ids:["unit-a","unit-b"],frozen_reserved_unit_ids:["unit-c"],baseline:{},conditions:[],evaluation_horizon_ticks:3,algorithm_version:"frozen-counterfactual-v1",status:"completed",created_at_utc:"2026-10-17T00:00:00Z",completed_at_utc:"2026-10-17T00:00:01Z",stale:false,stale_reason:null,reproduction:{isolation:"Dedicated analytical database."},error:null,results:{conditions:[{condition:{condition_id:"bridge",label:"Bridge closure",category:"bridge_closure",closed_asset_ids:["bridge-0"]},original_plan_feasibility:{feasible_assignments:0,total_original_assignments:1,invalidated_routes:1,assignments:[{unit_id:"unit-a",destination_id:"building-1",original_route_feasible:false,failure_reasons:["Original route contains an inaccessible road or bridge segment."]}]},reoptimized_plan:{status:"optimal_linear_sum_assignment",metrics:{reachable_priority_destinations:1,assigned_destinations:1,priority_weighted_coverage:45,coverage_denominator_priority_points:90,total_assigned_route_distance_m:120,maximum_synthetic_arrival_minutes:3,sum_synthetic_travel_minutes:3,resource_utilization:.5,unserved_destinations:0},missions:[mission],unreachable:[]},reliability:{status:"available",warnings:[]}}],critical_infrastructure:[{asset_id:"road-ns-0",dependent_assignments:1,affected_priority_weighted_coverage:45,feasible_after_closure:true,alternate_route_assignments:[]}],contingencies:[{contingency_id:"c1",trigger_condition:"Bridge closure",unit_id:"unit-a",destination_id:"building-1",route:mission.route,review_required:true,applied_to_live_operations:false}],baseline:{missions:[mission]},interpretation:"Conditions are deterministic.",study_runtime_ms:12}};

describe("Decision Robustness Lab",()=>{
  beforeEach(()=>vi.restoreAllMocks());
  it("freezes the baseline, presents hypothetical evidence, and keeps operational action unavailable",async()=>{
    const fetchMock=vi.fn().mockImplementation(async(input:RequestInfo|URL,init?:RequestInit)=>{
      const url=String(input);
      const payload=url.endsWith("robustness-baseline")?baseline:url.includes("?limit=10")?[]:init?.method==="POST"?{...completed,status:"pending",results:null}:completed;
      return {ok:true,status:200,json:async()=>payload} as Response;
    });
    vi.stubGlobal("fetch",fetchMock);
    render(<RobustnessLab city={city as unknown as CityState} scenario={scenario.state as unknown as ScenarioState}/>);
    expect(await screen.findByText("15")).toBeTruthy();
    fireEvent.click(screen.getByRole("button",{name:/run robustness study/i}));
    expect(await screen.findByText(/counterfactual result matrix/i)).toBeTruthy();
    expect(screen.getAllByText("Bridge closure").length).toBeGreaterThan(1);
    expect(screen.getByText(/HYPOTHETICAL · NO MISSION ANIMATION OR LIVE STATUS CHANGE/i)).toBeTruthy();
    expect(screen.getByText(/commander review required/i)).toBeTruthy();
    expect(screen.getByText(/not applied to live operations/i)).toBeTruthy();
    const post=fetchMock.mock.calls.find(call=>call[1]?.method==="POST");
    expect(post).toBeTruthy();
    const body=JSON.parse(String(post?.[1]?.body)) as {expected_state_version:number;expected_epoch:number;expected_infrastructure_revision:number;conditions:unknown[]};
    expect(body.expected_state_version).toBe(15);
    expect(body.expected_epoch).toBe(2);
    expect(body.expected_infrastructure_revision).toBe(4);
    expect(body.conditions).toHaveLength(4);
  });

  it("marks an old saved study historical in the compact operational summary",async()=>{
    const staleStudy={...completed,stale:true,stale_reason:"Infrastructure revision changed."};
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue({ok:true,status:200,json:async()=>[staleStudy]} as Response));
    render(<MemoryRouter><RobustnessSummary scenario={scenario.state as unknown as ScenarioState}/></MemoryRouter>);
    expect(await screen.findByText("HISTORICAL")).toBeTruthy();
    expect(screen.getByText(/source state or infrastructure changed/i)).toBeTruthy();
    expect(screen.getByRole("link",{name:/inspect saved study/i}).getAttribute("href")).toBe("/robustness");
  });
});
