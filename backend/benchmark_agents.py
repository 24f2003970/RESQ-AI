"""Run the fixed Part 6 event-to-recommendation performance scenario."""
import json
import gc
import tempfile
import time
from pathlib import Path

from app.agents import AgentOrchestrator
from app import ml_service
from app.rescue import PlanStore
from app.scenarios import ScenarioStore
from app.schemas import AdvanceRequest, ParameterUpdate, ScenarioCreate


def main():
    original_store=ml_service.store
    with tempfile.TemporaryDirectory(prefix="resq-part6-benchmark-") as directory:
        scenarios=ScenarioStore(Path(directory)/"benchmark.sqlite3")
        ml_service.store=scenarios
        state=scenarios.create(ScenarioCreate(name="Part 6 benchmark",seed=2026,preset="extreme"),"part6-benchmark-key").state
        state=scenarios.update_parameters(state.id,ParameterUpdate(rainfall_mm_h=300,river_level_m=5,
            drainage_effectiveness=0,speed=1,expected_version=state.state_version)).state
        state=scenarios.advance(state.id,AdvanceRequest(steps=120,single_step=True,expected_version=state.state_version)).state
        plans=PlanStore(scenarios.path)
        orchestrator=AgentOrchestrator(scenarios,plans)
        event=next(item for item in orchestrator.events(state.id) if item.event_type=="simulation_advanced")
        started=time.perf_counter();orchestrator.process_event(event.event_id);wall_ms=round((time.perf_counter()-started)*1000,3)
        detail=orchestrator.get_trace(event.event_id)
        report={
            "scenario":{"seed":2026,"preset":"extreme","rainfall_mm_h":300,"river_level_m":5,
                        "drainage_effectiveness":0,"steps":120,"tick":state.tick,
                        "affected_buildings":state.affected_buildings,"exposed_roads":state.exposed_roads},
            "event_id":event.event_id,"event_status":detail.event_status,"model_status":detail.trace.evidence["model_status"],
            "proposal_id":detail.trace.plan_id,"pipeline_wall_ms":wall_ms,
            "metrics":{key:detail.trace.evidence.get(key) for key in (
                "event_ingestion_ms","ml_inference_ms","routing_duration_ms",
                "resource_allocation_duration_ms","plan_persistence_duration_ms","pipeline_duration_ms")},
            "agent_durations_ms":detail.trace.evidence["agent_durations_ms"],
            "agent_statuses":{run.agent_name:run.status for run in detail.agents},
        }
        ml_service.store=original_store
        print(json.dumps(report,indent=2))
        orchestrator=None;plans=None;scenarios=None;state=None;detail=None;event=None
        gc.collect()


if __name__=="__main__":
    main()
