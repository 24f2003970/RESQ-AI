import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import AgentExplorer from "../components/AgentExplorer";
import scenarioFixture from "./fixtures/scenario.json";
import type { AgentDashboard, AgentEventEnvelope, AgentTraceDetail, ScenarioState } from "../api/client";

const api=vi.hoisted(()=>({dashboard:vi.fn(),events:vi.fn(),trace:vi.fn(),assess:vi.fn(),retry:vi.fn()}));
vi.mock("../api/client",async importOriginal=>({...await importOriginal<typeof import("../api/client")>(),fetchAgentDashboard:api.dashboard,fetchAgentEvents:api.events,fetchAgentTrace:api.trace,requestIntelligenceAssessment:api.assess,retryAgentEvent:api.retry}));
afterEach(()=>{vi.clearAllMocks()});
function LocationProbe(){const location=useLocation();return <output data-testid="location">{location.search}</output>}
const scenario=scenarioFixture.state as ScenarioState;
const definitions=["hazard_intelligence","impact_assessment","rescue_priority","routing","resource_allocation","commander_strategy"].map((name,index)=>({name,title:name.replaceAll("_"," "),responsibility:"Measured local output",position:index+1}));
const event={event_id:"event-real-1",event_type:"infrastructure_changed",scenario_id:scenario.id,scenario_epoch:scenario.epoch,simulation_tick:scenario.tick,simulation_state_version:scenario.state_version,infrastructure_revision:1,created_at_utc:"2026-10-15T10:00:00Z",source_module:"test",affected_entity_ids:["road-ew-1"],payload:{action:"close",road_id:"road-ew-1"},correlation_id:"correlation-1"} as AgentEventEnvelope;
const dashboard={scenario_id:scenario.id,scenario_epoch:scenario.epoch,simulation_state_version:scenario.state_version,infrastructure_revision:1,definitions,latest_runs:definitions.map((d)=>({run_id:`run-${d.position}`,event_id:event.event_id,correlation_id:event.correlation_id,scenario_id:scenario.id,scenario_epoch:scenario.epoch,simulation_state_version:scenario.state_version,infrastructure_revision:1,agent_name:d.name,status:"completed",input_hash:"hash",input_snapshot_ref:"snapshot",output_summary:{changed_routes:["unit-1|building-1"]},numerical_evidence:{route_pair_count:4},explanation:"Computed from the current graph.",attempt:1})),latest_trace:{trace_id:event.event_id,event_id:event.event_id,correlation_id:event.correlation_id,scenario_id:scenario.id,scenario_epoch:scenario.epoch,simulation_state_version:scenario.state_version,infrastructure_revision:1,status:"completed",plan_id:null,summary:"Bridge access changed; routing analysis completed.",evidence:{road_changes:["road-ew-1"]},created_at_utc:event.created_at_utc},pending_events:0,available_ground_units:3,reserved_ground_units:["unit-4"],commander_action_required:false,approved_route_review_required:false,approved_route_review_plan_ids:[]} as AgentDashboard;
const detail={event,event_status:"completed",attempts:1,agents:dashboard.latest_runs,trace:dashboard.latest_trace,related_plan:null} as AgentTraceDetail;

describe("AI Decision Explorer",()=>{
  it("shows persisted activity, event timeline, decision evidence and actual route changes",async()=>{
    api.dashboard.mockResolvedValue(dashboard);api.events.mockResolvedValue([event]);api.trace.mockResolvedValue(detail);
    render(<MemoryRouter><AgentExplorer scenario={scenario}/></MemoryRouter>);
    expect(await screen.findByText("Bridge access changed; routing analysis completed.")).toBeInTheDocument();
    expect(screen.getByText("infrastructure changed")).toBeInTheDocument();
    expect(screen.getByText("Computed from the current graph.")).toBeInTheDocument();
    expect(screen.getByText(/route_pair_count/)).toBeInTheDocument();
  });

  it("labels prior-epoch traces as historical and does not invent route content",async()=>{
    const historicDetail={...detail,event:{...event,scenario_epoch:scenario.epoch-1}};
    api.dashboard.mockResolvedValue(dashboard);api.events.mockResolvedValue([event]);api.trace.mockResolvedValue(historicDetail);
    render(<MemoryRouter><AgentExplorer scenario={scenario}/></MemoryRouter>);
    expect(await screen.findByText(new RegExp(`Historical trace from epoch ${scenario.epoch-1}`))).toBeInTheDocument();
    expect(screen.getByText(/Each recommendation stays a proposal/)).toBeInTheDocument();
  });

  it("shows the backend disconnected state",async()=>{
    api.dashboard.mockRejectedValue(new Error("local service offline"));api.events.mockRejectedValue(new Error("local service offline"));
    render(<MemoryRouter><AgentExplorer scenario={scenario}/></MemoryRouter>);
    await waitFor(()=>expect(screen.getByRole("alert")).toHaveTextContent("local service offline"));
  });

  it("queues an assessment and navigates to its trace ID",async()=>{
    api.dashboard.mockResolvedValue(dashboard);api.events.mockResolvedValue([event]);api.trace.mockResolvedValue(detail);api.assess.mockResolvedValue({event_id:"assessment-new"});
    render(<MemoryRouter><AgentExplorer scenario={scenario}/><LocationProbe/></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button",{name:"Run assessment"}));
    await waitFor(()=>expect(api.assess).toHaveBeenCalledWith(scenario.id));
    await waitFor(()=>expect(screen.getByTestId("location")).toHaveTextContent("event=assessment-new"));
  });
});
