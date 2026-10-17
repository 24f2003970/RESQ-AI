"""Run the bounded, disposable Part 15 scientific evaluation suite.

All SQLite state is created in temporary directories. The evaluation reports
one final observation per independent scenario group; ticks inside that group
are correlated and are not counted as separate disasters.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# ScenarioStore's module-level convenience store must also point at disposable
# storage while importing the existing application modules below.
_bootstrap = tempfile.TemporaryDirectory(prefix="resq-part15-bootstrap-")
os.environ["RESQ_DB_PATH"] = str(Path(_bootstrap.name) / "operational.sqlite3")

import numpy as np
import sklearn

from app.city_service import generate_city
from app.ml_service import ModelUnavailable, predict_state
from app.rescue import generate_plan
from app.scenarios import ScenarioStore
from app.schemas import AdvanceRequest, ImpactItem, ParameterUpdate, ScenarioCreate


SEED_BASE = 151500
TICKS = 6
CASES = [
    {"case": "mild_demo_rainfall", "preset": "mild", "rainfall": 30.0, "river": 0.6, "drainage": 0.2},
    {"case": "moderate_flood", "preset": "heavy", "rainfall": 75.0, "river": 0.25, "drainage": 0.5},
    {"case": "severe_flood", "preset": "extreme", "rainfall": 180.0, "river": 1.4, "drainage": 0.2},
    {"case": "increased_river_stage", "preset": "heavy", "rainfall": 40.0, "river": 1.1, "drainage": 0.55},
    {"case": "reduced_drainage", "preset": "heavy", "rainfall": 55.0, "river": 0.2, "drainage": 0.05},
    {"case": "important_road_closure", "preset": "mild", "rainfall": 30.0, "river": 0.6, "drainage": 0.2, "closures": ["road-ns-2"]},
    {"case": "bridge_disruption", "preset": "mild", "rainfall": 30.0, "river": 0.6, "drainage": 0.2, "closed_bridge": "bridge-2"},
    {"case": "limited_rescue_resources", "preset": "heavy", "rainfall": 65.0, "river": 0.3, "drainage": 0.4, "ambulances": 1, "teams": 1},
    {"case": "model_unavailable_fallback", "preset": "mild", "rainfall": 30.0, "river": 0.6, "drainage": 0.2, "model_unavailable": True},
    {"case": "graph_inaccessible_all_roads_closed", "preset": "mild", "rainfall": 30.0, "river": 0.6, "drainage": 0.2, "all_roads_closed": True},
]


def sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _set_bridge_closed(state, bridge_id: str):
    bridges = [
        item.model_copy(update={"status": "closed"}) if item.entity_id == bridge_id else item
        for item in state.impacts.bridges
    ]
    return state.model_copy(update={"impacts": state.impacts.model_copy(update={"bridges": bridges})})


def evaluate_case(case: dict, index: int) -> dict:
    seed = SEED_BASE + index
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix=f"resq-part15-{case['case']}-") as temp:
        db_path = Path(temp) / "disposable.sqlite3"
        store = ScenarioStore(db_path)
        created = store.create(
            ScenarioCreate(name=f"Part 15 {case['case']}", seed=seed, preset=case["preset"]),
            idempotency_key=f"part15:{case['case']}:{seed}",
        )
        state = created.state
        state = store.update_parameters(
            state.id,
            ParameterUpdate(
                rainfall_mm_h=case["rainfall"], river_level_m=case["river"],
                drainage_effectiveness=case["drainage"], expected_version=state.state_version,
            ),
        ).state
        state = store.advance(
            state.id, AdvanceRequest(steps=TICKS, single_step=True, expected_version=state.state_version),
        ).state
        city = generate_city(seed)

        if "ambulances" in case or "teams" in case:
            ambulance_limit = case.get("ambulances", sum(unit.type == "ambulance" for unit in city.rescue_units))
            team_limit = case.get("teams", sum(unit.type == "rescue_team" for unit in city.rescue_units))
            ambulances = [unit for unit in city.rescue_units if unit.type == "ambulance"][:ambulance_limit]
            teams = [unit for unit in city.rescue_units if unit.type == "rescue_team"][:team_limit]
            boats = [unit for unit in city.rescue_units if unit.type == "boat"]
            city = city.model_copy(update={"rescue_units": [*ambulances, *teams, *boats]})

        if case.get("closed_bridge"):
            state = _set_bridge_closed(state, case["closed_bridge"])

        closures = list(case.get("closures", []))
        if case.get("all_roads_closed"):
            closures = [road.id for road in city.roads]

        ml_status = "ready"
        ml_error = None
        if case.get("model_unavailable"):
            # Exercise the product's explicit degraded-input path without
            # deleting or altering the installed production model artifacts.
            prediction_set = type("UnavailablePredictions", (), {"predictions": []})()
            ml_status = "unavailable_simulated_fallback"
            ml_error = "Evaluation deliberately supplied no future-exposure predictions."
        else:
            try:
                prediction_set = predict_state(state)
            except ModelUnavailable as exc:
                prediction_set = type("UnavailablePredictions", (), {"predictions": []})()
                ml_status = "unavailable"
                ml_error = str(exc)

        plan_started = time.perf_counter()
        plan = generate_plan(city, state, prediction_set, closures)
        wall_ms = round((time.perf_counter() - started) * 1000, 3)
        comparison = plan.comparison
        base = comparison["baseline"]
        optimized = comparison["optimized"]
        objective_delta = round(optimized["objective_value"] - base["objective_value"], 3)
        weighted_delta = round(optimized["priority_weighted_coverage"] - base["priority_weighted_coverage"], 3)
        return {
            "scenario_group": f"part15-seed-{seed}",
            "case": case["case"],
            "seed": seed,
            "ticks_within_group": TICKS,
            "tick_observations_counted_as_independent": 1,
            "configuration": {key: case[key] for key in ("preset", "rainfall", "river", "drainage")},
            "infrastructure": {"manual_road_closures": sorted(closures), "closed_bridge": case.get("closed_bridge"), "all_roads_closed": bool(case.get("all_roads_closed"))},
            "resource_inventory": {"ground_unit_count": sum(unit.type != "boat" for unit in city.rescue_units), "ambulance_count": sum(unit.type == "ambulance" for unit in city.rescue_units), "team_count": sum(unit.type == "rescue_team" for unit in city.rescue_units)},
            "physical_state": {"tick": state.tick, "maximum_flood_depth_m": state.maximum_depth_m, "physically_affected_buildings": state.affected_buildings, "exposed_roads": state.exposed_roads, "closed_bridges": state.closed_bridges},
            "ml": {"status": ml_status, "unavailable_reason": ml_error, "predicted_rows": len(getattr(prediction_set, "predictions", []))},
            "planner": {"solver_status": plan.solver_status, "objective_definition": plan.objective, "unreachable_destinations": len(plan.unreachable), "supported_unit_destination_routes": len(plan.available_assignments), "assignment_runtime_ms": plan.timings_ms.get("assignment"), "routing_runtime_ms": plan.timings_ms.get("routing"), "planning_wall_ms": round((time.perf_counter() - plan_started) * 1000, 3), "conventional_baseline": base, "optimized": optimized, "optimized_minus_baseline": {"objective_value": objective_delta, "priority_weighted_coverage": weighted_delta, "destinations_covered": optimized["destinations_covered"] - base["destinations_covered"], "total_distance_m": round(optimized["total_distance_m"] - base["total_distance_m"], 1), "simulated_travel_minutes": round(optimized["total_simulated_travel_minutes"] - base["total_simulated_travel_minutes"], 1)}},
            "scenario_runtime_ms": wall_ms,
        }


def run(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    results = [evaluate_case(case, index) for index, case in enumerate(CASES)]
    metric = "objective_value"
    deltas = [row["planner"]["optimized_minus_baseline"][metric] for row in results]
    summary = {
        "independent_scenario_groups": len(results),
        "ticks_per_group": TICKS,
        "scenario_seed_range": [results[0]["seed"], results[-1]["seed"]],
        "assignment_objective_outcomes": {"improved": sum(value > 0.005 for value in deltas), "equal_within_0_01": sum(abs(value) <= 0.01 for value in deltas), "lower": sum(value < -0.005 for value in deltas)},
        "groups_with_zero_ground_assignments": sum(row["planner"]["optimized"]["destinations_covered"] == 0 for row in results),
        "all_roads_closed_assignments": next(row["planner"]["optimized"]["destinations_covered"] for row in results if row["case"] == "graph_inaccessible_all_roads_closed"),
        "total_runtime_ms": round((time.perf_counter() - started) * 1000, 3),
    }
    artifacts = Path(__file__).resolve().parent / "ml_artifacts"
    report = {
        "title": "RESQ-AI Part 15 bounded scientific evaluation",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Synthetic simulator and synthetic graph only; not an operational safety or field-performance evaluation.",
        "reproduction": "cd backend; .\\.venv\\Scripts\\python.exe run_part15_evaluation.py",
        "method": {"scenario_groups": "Ten independent deterministic seeds; one final state and one planner comparison per generated group.", "within_group_ticks": f"{TICKS} deterministic five-minute flood ticks; correlated ticks are not counted as independent observations.", "planner_comparison": "The current conventional nearest-feasible-unit baseline and current SciPy linear-sum assignment use the same frozen state, priority destinations, unit inventory, route map, graph, depth constraints, closures, bridge state, and route costs.", "routing": "The current shared NetworkX router with synthetic 90 m endpoint access-spur limit, modeled flood/bridge/manual-closure state, and unit-specific depth rules.", "evaluation_database": "Each group uses a disposable temporary SQLite database. It is removed after that case completes; no operational scenario database is opened for writes."},
        "environment": {"os": platform.platform(), "python": platform.python_version(), "numpy": np.__version__, "scikit_learn": sklearn.__version__},
        "model_artifact_sha256": sha256(artifacts / "flood_exposure_v1.joblib"),
        "calibrator_artifact_sha256": sha256(artifacts / "flood_exposure_platt_v1.joblib"),
        "summary": summary,
        "scenario_groups": results,
        "limitations": ["Ten scenario groups cover specified conditions but do not estimate real-world outcome rates.", "Scenario seeds are distinct; configuration families are not repeated enough for inferential comparisons.", "Ground-truth flood exposure and ML labels come from the same synthetic simulator family.", "Travel speeds, route connectivity, access spurs, and occupant counts are synthetic assumptions.", "Model-unavailable fallback is supplied deliberately to exercise degraded planning, not caused by removing production files."],
    }
    json_path = output_dir / "scientific_evaluation.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    columns = ["scenario_group", "case", "seed", "tick", "physical_max_depth_m", "affected_buildings", "ml_status", "solver_status", "baseline_assignments", "optimized_assignments", "baseline_priority_coverage", "optimized_priority_coverage", "baseline_objective", "optimized_objective", "objective_delta", "baseline_unreachable", "optimized_unreachable", "assignment_runtime_ms", "routing_runtime_ms", "scenario_runtime_ms"]
    with (output_dir / "scientific_evaluation.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in results:
            base = row["planner"]["conventional_baseline"]
            opt = row["planner"]["optimized"]
            writer.writerow({"scenario_group": row["scenario_group"], "case": row["case"], "seed": row["seed"], "tick": row["physical_state"]["tick"], "physical_max_depth_m": row["physical_state"]["maximum_flood_depth_m"], "affected_buildings": row["physical_state"]["physically_affected_buildings"], "ml_status": row["ml"]["status"], "solver_status": row["planner"]["solver_status"], "baseline_assignments": base["destinations_covered"], "optimized_assignments": opt["destinations_covered"], "baseline_priority_coverage": base["priority_weighted_coverage"], "optimized_priority_coverage": opt["priority_weighted_coverage"], "baseline_objective": base["objective_value"], "optimized_objective": opt["objective_value"], "objective_delta": row["planner"]["optimized_minus_baseline"]["objective_value"], "baseline_unreachable": base["unreachable_destinations"], "optimized_unreachable": opt["unreachable_destinations"], "assignment_runtime_ms": row["planner"]["assignment_runtime_ms"], "routing_runtime_ms": row["planner"]["routing_runtime_ms"], "scenario_runtime_ms": row["scenario_runtime_ms"]})
    lines = ["# Part 15 scientific evaluation run", "", f"Generated: {report['generated_at_utc']}", "", f"- Independent scenario groups: **{summary['independent_scenario_groups']}**.", f"- Flood ticks per group (correlated within scenario): **{TICKS}**.", f"- Optimized objective compared with baseline: **{summary['assignment_objective_outcomes']['improved']} improved, {summary['assignment_objective_outcomes']['equal_within_0_01']} effectively equal, {summary['assignment_objective_outcomes']['lower']} lower**.", f"- Groups with zero assignments: **{summary['groups_with_zero_ground_assignments']}**.", f"- All-roads-closed assignments: **{summary['all_roads_closed_assignments']}**.", f"- Total local runtime: **{summary['total_runtime_ms']:.3f} ms**.", "", "See `scientific_evaluation.json` for per-group conditions, full metrics and environment; `scientific_evaluation.csv` is the compact machine-readable table.", "", "These are synthetic simulator results. They do not establish real-world rescue performance or field safety.", ""]
    (output_dir / "scientific_evaluation.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    default = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "part15"
    parser.add_argument("--output", type=Path, default=default, help="Output directory (default: docs/evidence/part15)")
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({"summary": result["summary"], "outputs": [str(args.output / name) for name in ("scientific_evaluation.json", "scientific_evaluation.csv", "scientific_evaluation.md")]}, indent=2))


if __name__ == "__main__":
    main()
    _bootstrap.cleanup()
