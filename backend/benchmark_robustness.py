"""Run the bounded 11-case deterministic Part 13 laptop benchmark.

This command creates only temporary SQLite databases and prints the measured
case outcomes and wall-clock values as JSON. It never targets the demo database.
"""
from __future__ import annotations

import json
import gc
import tempfile
import time
from pathlib import Path

from app.city_service import generate_city
from app.experiments import ExperimentRepository
from app.ml_service import ModelUnavailable, predict_state
from app.rescue import PlanStore, generate_plan
from app.robustness import (Counterfactual, RobustnessRepository, RobustnessRunner,
    RobustnessStudyCreate, read_infrastructure, read_reserved_units)
from app.scenarios import ScenarioStore
from app.schemas import AdvanceRequest, ParameterUpdate, ScenarioCreate


def main():
    with tempfile.TemporaryDirectory(prefix="resq-part13-benchmark-") as directory:
        root = Path(directory)
        live = root / "benchmark.sqlite3"
        scenarios = ScenarioStore(live)
        state = scenarios.create(ScenarioCreate(name="Part 13 deterministic stress", seed=2026, preset="extreme"), "part13-benchmark-seed-2026").state
        state = scenarios.update_parameters(state.id, ParameterUpdate(expected_version=state.state_version,
            rainfall_mm_h=300, river_level_m=2.5, drainage_effectiveness=0)).state
        for _ in range(12):
            state = scenarios.advance(state.id, AdvanceRequest(steps=1, single_step=True,
                expected_version=state.state_version)).state
        city = generate_city(state.seed)
        plans = PlanStore(live)
        revision, closures = read_infrastructure(live,state.id,state.epoch)
        reserved = read_reserved_units(live,state.id,state.epoch)
        try:
            predictions = predict_state(state)
            reliability = predictions.reliability_status
        except ModelUnavailable as exc:
            predictions = None
            reliability = f"unavailable: {exc}"
        plan = generate_plan(city,state,predictions,closures,infrastructure_revision=revision,reserved_unit_ids=reserved)
        primary_route = next((mission["route"] for mission in plan.missions if mission["route"].get("road_ids")), None)
        primary_road = primary_route["road_ids"][0] if primary_route else city.roads[0].id
        used_roads = {road for mission in plan.missions for road in mission["route"].get("road_ids", [])}
        alternative_bridge = next((bridge for bridge in city.bridges if bridge.road_id not in used_roads), city.bridges[0])
        ambulance_ids = sorted(unit.id for unit in city.rescue_units if unit.type=="ambulance" and unit.status=="standby")
        ground_ids = sorted(unit.id for unit in city.rescue_units if unit.type=="rescue_team" and unit.status=="standby")
        conditions = [
            Counterfactual(condition_id="stable-baseline",label="Stable baseline",category="baseline"),
            Counterfactual(condition_id="flood-escalation",label="Flood escalation",category="environment",rainfall_mm_h=300,river_level_m=3.0,drainage_effectiveness=0),
            Counterfactual(condition_id="primary-route-closed",label=f"Primary road {primary_road} closed; alternate bridge remains open",category="road_closure",closed_asset_ids=[primary_road]),
            Counterfactual(condition_id="backup-bridge-closed",label=f"Hypothetical alternate bridge {alternative_bridge.id} closed",category="bridge_closure",closed_asset_ids=[alternative_bridge.id]),
            Counterfactual(condition_id="all-ground-roads-closed",label="All modeled road corridors closed",category="road_closure",closed_asset_ids=[road.id for road in city.roads]),
            Counterfactual(condition_id="ambulance-unavailable",label="One ambulance unavailable",category="resources",unavailable_unit_type="ambulance",unavailable_count=1),
            Counterfactual(condition_id="multiple-unavailable",label="Two ground units unavailable",category="resources",unavailable_unit_ids=(ambulance_ids+ground_ids)[:2]),
            Counterfactual(condition_id="model-unavailable",label="Model unavailable; physical fallback",category="ml_reliability",reliability_mode="injected_unavailable"),
            Counterfactual(condition_id="support-degraded",label="Out-of-support predictions excluded",category="ml_reliability",reliability_mode="outside_support"),
            Counterfactual(condition_id="no-forecast-eligible",label="No forecast-only destinations eligible",category="ml_reliability",reliability_mode="no_forecast_destinations"),
            Counterfactual(condition_id="restored-resource-analysis",label="Full frozen inventory restored for a new independent analysis",category="baseline"),
        ]
        analytics = root / "experiments.sqlite3"
        ExperimentRepository(analytics)
        repository = RobustnessRepository(analytics)
        runner = RobustnessRunner(repository)
        available = sorted(unit.id for unit in city.rescue_units if unit.status=="standby" and unit.type!="boat" and unit.id not in set(reserved))
        request = RobustnessStudyCreate(scenario_id=state.id,expected_state_version=state.state_version,
            expected_epoch=state.epoch,expected_infrastructure_revision=revision,
            evaluation_horizon_ticks=3,conditions=conditions)
        study = repository.create(request,state,revision,available,reserved,plan,
            {"missions":plan.missions,"metrics":plan.comparison["optimized"]})
        started = time.perf_counter()
        runner.run(study.study_id)
        elapsed_ms = round((time.perf_counter()-started)*1000,3)
        completed = repository.get(study.study_id)
        if not completed or completed.status != "completed":
            raise RuntimeError(completed.error if completed else "Study record disappeared.")
        cases = []
        for result in completed.results["conditions"]:
            cases.append({"condition_id":result["condition"]["condition_id"],
                "label":result["condition"]["label"],
                "original_feasible_assignments":result["original_plan_feasibility"]["feasible_assignments"],
                "original_assignment_count":result["original_plan_feasibility"]["total_original_assignments"],
                "invalidated_routes":result["original_plan_feasibility"]["invalidated_routes"],
                "reoptimized_assignments":result["reoptimized_plan"]["metrics"]["assigned_destinations"],
                "unserved_destinations":result["reoptimized_plan"]["unserved_destinations"],
                "solver_status":result["reoptimized_plan"]["status"],
                "condition_runtime_ms":result["timing_ms"]["condition_total"]})
        print(json.dumps({"seed":2026,"starting_tick":12,"evaluation_horizon_ticks":3,
            "model_reliability":reliability,"baseline_assignment_count":len(plan.missions),
            "study_runtime_ms":elapsed_ms,"persisted_payload_bytes":len(json.dumps(completed.model_dump(mode="json")).encode()),
            "cases":cases},indent=2))
        del runner, repository, plans, scenarios
        gc.collect()


if __name__ == "__main__":
    main()
