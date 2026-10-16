"""Run the signature Part 7 journey against real local simulation and ML artifacts.

From backend/: .venv/Scripts/python.exe demo_acceptance.py
This is an integration acceptance run; it writes only to a temporary SQLite DB.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import time
from pathlib import Path

from app.agents import AGENT_NAMES, AgentOrchestrator
from app.ml_service import ModelUnavailable, model_info
from app.rescue import PlanStore
from app.scenarios import ScenarioStore
from app.schemas import AdvanceRequest, ParameterUpdate, ScenarioCreate


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    report: dict = {"status": "FAIL", "checks": [], "evidence": {}}
    started = time.perf_counter()
    model = model_info()
    require(model.status == "ready", f"Local ML artifact unavailable: {model.unavailable_reason}")
    report["checks"].append("Local self-trained model artifact loads successfully")
    with tempfile.TemporaryDirectory(prefix="resq-part7-demo-", ignore_cleanup_errors=True) as folder:
        path = Path(folder) / "demo.sqlite3"
        scenarios = ScenarioStore(path)
        plans = PlanStore(path)
        # AgentOrchestrator calls the production predictions() function; point
        # its module-level live store at this isolated acceptance scenario.
        from app import ml_service
        ml_service.store = scenarios
        envelope = scenarios.create(ScenarioCreate(name="Part 7 acceptance · seed 2026", seed=2026, preset="mild"), "part7-acceptance")
        state = envelope.state
        report["evidence"]["scenario_id"] = state.id
        report["checks"].append("Initial mild scenario created with seed 2026")

        orchestrator = AgentOrchestrator(scenarios, plans)
        changed = scenarios.update_parameters(state.id, ParameterUpdate(rainfall_mm_h=90, river_level_m=1.4,
            drainage_effectiveness=0.2, expected_version=state.state_version)).state
        flood_started = time.perf_counter()
        flooded = scenarios.advance(state.id, AdvanceRequest(steps=12, single_step=True,
            expected_version=changed.state_version)).state
        report["evidence"]["flood_runtime_ms"] = round((time.perf_counter() - flood_started) * 1000, 1)
        report["evidence"]["flood_tick"] = flooded.tick
        report["evidence"]["affected_buildings"] = flooded.affected_buildings
        report["evidence"]["exposed_roads"] = flooded.exposed_roads
        require(flooded.tick == 12, "Flood progression did not reach 12 ticks.")
        require(flooded.affected_buildings > 0, "Severe forcing did not produce meaningful building exposure.")
        report["checks"].append("Severe flood advanced through 12 deterministic five-minute ticks with nonzero exposure")

        from app.ml_service import predict_state
        predictions = predict_state(flooded)
        require(bool(predictions.predictions), "Local inference returned no building predictions.")
        report["evidence"]["model_version"] = predictions.model_version
        report["evidence"]["predicted_future_exposed"] = sum(item.predicted_future_exposed for item in predictions.predictions)
        report["checks"].append("Local ML inference ran against the saved flood snapshot")

        flood_event = next(event for event in orchestrator.events(state.id)
                           if event.event_type == "simulation_advanced" and event.simulation_state_version == flooded.state_version)
        require(flood_event.scenario_id == state.id, f"Outbox scenario mismatch: {flood_event.scenario_id} != {state.id}")
        scenarios.get(flood_event.scenario_id)
        orchestrator.process_event(flood_event.event_id)
        trace = orchestrator.get_trace(flood_event.event_id)
        with sqlite3.connect(path) as db:
            outbox_error = db.execute("SELECT error FROM agent_event_outbox WHERE event_id=?", (flood_event.event_id,)).fetchone()[0]
        require(trace.event_status in ("completed", "degraded"), f"Initial agent pipeline ended {trace.event_status}: "
                + f" event_error={outbox_error}; trace={trace.trace.summary if trace.trace else 'no trace'}; "
                + "; ".join(f"{run.agent_name}:{run.status}:{run.error or run.explanation}" for run in trace.agents))
        require([run.agent_name for run in trace.agents] == AGENT_NAMES, "The ordered six-agent trace is incomplete.")
        proposal = plans.by_trigger(flood_event.event_id)
        require(proposal is not None and proposal.status == "proposed", "Flood event did not produce a fresh human-review proposal.")
        route_mission = next((mission for mission in proposal.missions if mission["route"]["road_ids"]), None)
        require(route_mission is not None, "Proposal contains no valid graph-following route.")
        report["evidence"].update({"flood_event_id": flood_event.event_id, "initial_plan_id": proposal.plan_id,
            "agent_status": trace.event_status, "agent_count": len(trace.agents), "route_unit": route_mission["unit_id"],
            "route_destination": route_mission["destination_id"], "route_before": route_mission["route"]["road_ids"]})
        report["checks"].append("Six-agent event pipeline persisted a commander-review proposal with a computed route")

        road_id = route_mission["route"]["road_ids"][0]
        revision, _ = plans.infrastructure(state.id, flooded.epoch)
        with sqlite3.connect(path) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO road_closures(scenario_id,epoch,road_id,reason,active) VALUES(?,?,?, ?,1)",
                       (state.id, flooded.epoch, road_id, "Part 7 acceptance route disruption"))
            db.execute("UPDATE scenario_infrastructure SET revision=revision+1 WHERE scenario_id=? AND epoch=?", (state.id, flooded.epoch))
            db.commit()
        new_revision, closures = plans.infrastructure(state.id, flooded.epoch)
        require(new_revision == revision + 1, "Infrastructure revision did not increment after road closure.")
        closure_event = orchestrator.enqueue(event_type="infrastructure_changed", scenario_id=state.id, state=flooded,
            infrastructure_revision=new_revision, source_module="part7_acceptance",
            payload={"road_id": road_id, "action": "close", "active_manual_closures": closures})
        orchestrator.process_event(closure_event.event_id)
        closure_trace = orchestrator.get_trace(closure_event.event_id)
        fresh = plans.by_trigger(closure_event.event_id)
        require(proposal.status == "proposed", "Unexpected in-memory proposal status mutation.")
        superseded = plans.get(proposal.plan_id)
        require(superseded is not None and superseded.status == "superseded", "Old proposal was not invalidated by closure revision.")
        require(closure_trace.event_status in ("completed", "degraded"), "Closure-triggered agent pipeline did not complete.")
        require(fresh is not None and fresh.status == "proposed", "Closure event produced no fresh human-review proposal.")
        same_pair = next((item for item in fresh.available_assignments if item["unit_id"] == route_mission["unit_id"]
                          and item["destination_id"] == route_mission["destination_id"]), None)
        after_route = same_pair["route"]["road_ids"] if same_pair else None
        route_changed = after_route is None or after_route != route_mission["route"]["road_ids"]
        require(route_changed, "Chosen relevant road closure did not change the route or accessibility.")
        report["evidence"].update({"closure_event_id": closure_event.event_id, "infrastructure_revision_before": revision,
            "infrastructure_revision_after": new_revision, "closed_road_id": road_id, "old_plan_status": superseded.status,
            "fresh_plan_id": fresh.plan_id, "route_after": after_route, "route_changed_or_unreachable": route_changed,
            "closure_agent_status": closure_trace.event_status})
        report["checks"].append("Route-relevant closure incremented revision, invalidated old proposal, and produced a verified changed/unreachable route")

        require(fresh.status == "proposed", "A fresh proposal must remain under human review.")
        plans.decision(fresh.plan_id, "approved", reason="Explicit acceptance-script human decision", expected_version=flooded.state_version)
        approval_event = next(event for event in orchestrator.events(state.id) if event.event_type == "rescue_plan_approved"
                              and event.payload.get("plan_id") == fresh.plan_id)
        orchestrator.process_event(approval_event.event_id)
        approval_trace = orchestrator.get_trace(approval_event.event_id)
        next_proposal = plans.by_trigger(approval_event.event_id)
        approved_units = {mission["unit_id"] for mission in fresh.missions}
        next_units = {mission["unit_id"] for mission in next_proposal.missions} if next_proposal else set()
        require(not (approved_units & next_units), "A subsequent proposal double-allocated an approved unit.")
        require(approval_trace.event_status in ("completed", "degraded"), "Persisted commander decision trace is missing.")
        report["evidence"].update({"approval_event_id": approval_event.event_id, "approved_plan_id": fresh.plan_id,
            "approved_units": sorted(approved_units), "subsequent_plan_id": next_proposal.plan_id if next_proposal else None,
            "subsequent_units": sorted(next_units), "approval_trace_status": approval_trace.event_status})
        report["checks"].append("Commander approval was explicit, its decision trace persisted, and approved units were not assigned again")

    report["status"] = "PASS"
    report["runtime_seconds"] = round(time.perf_counter() - started, 2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ModelUnavailable, StopIteration) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2))
        raise SystemExit(1) from exc
