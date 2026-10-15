import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import RescuePlanning from "../components/RescuePlanning";
import cityFixture from "./fixtures/city.json";
import scenarioFixture from "./fixtures/scenario.json";
import type { CityState, ScenarioState } from "../api/client";

afterEach(()=>vi.unstubAllGlobals());

const city=cityFixture as CityState;
const scenario=scenarioFixture.state as ScenarioState;
const route={reachable:true,distance_m:180,simulated_minutes:1.2,road_ids:["road-ew-1"],edge_ids:["road-ew-1:edge"],polyline:[[-150,-80],[-100,-80]],accessibility:"open",explanation:"Dijkstra"};
const plan={plan_id:"plan-1",scenario_id:scenario.id,scenario_version:scenario.state_version,simulation_tick:scenario.tick,generated_at:"2026-01-01T00:00:00Z",status:"proposed",priorities:[{building_id:city.buildings[0].id,name:"Test Zone",priority_score:72,explanation:"Computed components."}],missions:[{unit_id:"unit-1",destination_id:city.buildings[0].id,unit_capacity:2,occupants_targeted:2,route}],available_assignments:[{unit_id:"unit-1",destination_id:city.buildings[0].id,unit_capacity:2,occupants_targeted:2,route}],unreachable:[],comparison:{baseline:{destinations_covered:1,total_distance_m:180},optimized:{destinations_covered:1,total_distance_m:180}},solver_status:"optimal_exact_enumeration",objective:"Synthetic objective",explanation:"Recommendation only."};

function response(payload:unknown){return Promise.resolve(new Response(JSON.stringify(payload),{status:200,headers:{"Content-Type":"application/json"}}));}

describe("Rescue Planning panel",()=>{
  it("renders backend missions and requires an explicit commander decision",async()=>{
    const fetchMock=vi.fn((input:RequestInfo|URL,init?:RequestInit)=>{
      const url=String(input);
      if(url.endsWith("/rescue-plans"))return response(plan);
      if(url.endsWith("/decision"))return response({...plan,status:"approved"});
      throw new Error(`Unexpected API request ${init?.method} ${url}`);
    });
    vi.stubGlobal("fetch",fetchMock);
    render(<RescuePlanning city={city} scenario={scenario} onPlan={()=>{}}/>);
    fireEvent.click(screen.getByRole("button",{name:"Generate recommendation"}));
    expect((await screen.findAllByText(/unit-1 →/)).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/synthetic minutes/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button",{name:"Approve plan"}));
    await waitFor(()=>expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/decision"),expect.objectContaining({method:"POST"})));
    expect(await screen.findByText("approved")).toBeInTheDocument();
  });
});
