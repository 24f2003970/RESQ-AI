"""Frozen-snapshot, analytical rescue-plan robustness studies.

Studies are stored in the experiment database and only read operational state.
The worker evaluates the saved plan as-is before asking the existing planner for
a separate counterfactual alternative. No output from this module is an action.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .city_service import generate_city
from .flood import SimulationParameters as FloodSimulationParameters, channel_mask, impact_assessment, step
from .ml_service import ModelUnavailable, predict_state
from .rescue import PlanStore, RescuePlan, build_road_graph, generate_plan, route
from .schemas import ImpactAssessment, MassBalance, ScenarioState, SimulationParameters as ScenarioParameters
from .scenarios import ScenarioError

ROBUSTNESS_ALGORITHM_VERSION = "frozen-counterfactual-v1"
MAX_VARIANTS = 12
MAX_HORIZON_TICKS = 12
PRIORITY_THRESHOLD = 70.0


class Counterfactual(BaseModel):
    model_config = ConfigDict(extra="forbid")
    condition_id: str = Field(min_length=1, max_length=48, pattern=r"^[a-zA-Z0-9_-]+$")
    label: str = Field(min_length=1, max_length=80)
    category: Literal["baseline", "environment", "road_closure", "bridge_closure", "resources", "ml_reliability"]
    rainfall_mm_h: float | None = Field(default=None, ge=0, le=300)
    river_level_m: float | None = Field(default=None, ge=-2, le=5)
    drainage_effectiveness: float | None = Field(default=None, ge=0, le=1)
    closed_asset_ids: list[str] = Field(default_factory=list, max_length=20)
    unavailable_unit_ids: list[str] = Field(default_factory=list, max_length=8)
    unavailable_unit_type: Literal["ambulance", "rescue_team"] | None = None
    unavailable_count: int = Field(default=0, ge=0, le=4)
    reliability_mode: Literal["actual", "injected_unavailable", "outside_support", "no_forecast_destinations"] = "actual"

    @model_validator(mode="after")
    def valid_intervention(self):
        if len(set(self.closed_asset_ids)) != len(self.closed_asset_ids):
            raise ValueError("Infrastructure assets may appear only once.")
        if len(set(self.unavailable_unit_ids)) != len(self.unavailable_unit_ids):
            raise ValueError("Unavailable units may appear only once.")
        if self.category == "environment" and all(v is None for v in (self.rainfall_mm_h, self.river_level_m, self.drainage_effectiveness)):
            raise ValueError("An environmental condition must change at least one forcing parameter.")
        if self.category in ("road_closure", "bridge_closure") and not self.closed_asset_ids:
            raise ValueError("An infrastructure condition must identify at least one asset.")
        if self.category == "resources" and not (self.unavailable_unit_ids or (self.unavailable_unit_type and self.unavailable_count)):
            raise ValueError("A resource condition must identify unavailable inventory.")
        if self.category == "ml_reliability" and self.reliability_mode == "actual":
            raise ValueError("Choose an explicit reliability failure injection or outside-support evaluation.")
        return self


class RobustnessStudyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_id: str = Field(min_length=1, max_length=128)
    expected_state_version: int = Field(ge=1)
    expected_epoch: int = Field(ge=0)
    expected_infrastructure_revision: int = Field(ge=0)
    original_plan_id: str | None = None
    evaluation_horizon_ticks: int = Field(default=0, ge=0, le=MAX_HORIZON_TICKS)
    conditions: list[Counterfactual] = Field(min_length=1, max_length=MAX_VARIANTS)

    @model_validator(mode="after")
    def unique_conditions(self):
        ids = [condition.condition_id for condition in self.conditions]
        if len(ids) != len(set(ids)):
            raise ValueError("Condition IDs must be unique.")
        if self.evaluation_horizon_ticks < 1 and any(item.category == "environment" for item in self.conditions):
            raise ValueError("Environmental counterfactuals require at least one authoritative flood-simulation tick.")
        return self


class RobustnessStudy(BaseModel):
    study_id: str
    scenario_id: str
    scenario_epoch: int
    simulation_state_version: int
    infrastructure_revision: int
    simulation_tick: int
    seed: int
    original_plan_id: str
    snapshot_sha256: str
    frozen_available_unit_ids: list[str]
    frozen_reserved_unit_ids: list[str]
    frozen_resource_positions: dict[str, dict]
    baseline: dict
    conditions: list[Counterfactual]
    evaluation_horizon_ticks: int
    algorithm_version: str
    status: Literal["pending", "running", "completed", "failed", "interrupted"]
    created_at_utc: str
    completed_at_utc: str | None = None
    stale: bool = False
    stale_reason: str | None = None
    results: dict | None = None
    reproduction: dict
    error: str | None = None


class RobustnessRepository:
    """Dedicated analytical table in the existing experiments SQLite file."""
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._lock = Lock()
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS robustness_studies (
                study_id TEXT PRIMARY KEY, scenario_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE, snapshot_json TEXT NOT NULL,
                original_plan_json TEXT NOT NULL, request_json TEXT NOT NULL,
                record_json TEXT NOT NULL, created_at_utc TEXT NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS robustness_by_scenario ON robustness_studies(scenario_id,created_at_utc DESC)")
            rows = db.execute("SELECT study_id,record_json FROM robustness_studies").fetchall()
            for study_id, raw in rows:
                record = json.loads(raw)
                if record.get("status") in ("pending", "running"):
                    record["status"] = "interrupted"
                    record["error"] = "Local service restarted before the study finished; saved inputs are retained. Start a new study to recompute."
                    db.execute("UPDATE robustness_studies SET record_json=? WHERE study_id=?", (json.dumps(record), study_id))

    def create(self, request: RobustnessStudyCreate, state: ScenarioState, revision: int,
               available_ids: list[str], reserved_ids: list[str], original: RescuePlan,
               baseline: dict, resource_positions: dict[str, dict] | None = None) -> RobustnessStudy:
        if (request.scenario_id, request.expected_state_version, request.expected_epoch,
            request.expected_infrastructure_revision) != (state.id, state.state_version, state.epoch, revision):
            raise ScenarioError(409, "Study inputs do not match the frozen scenario and infrastructure snapshot.")
        if (original.scenario_id, original.scenario_version, original.scenario_epoch,
            original.infrastructure_revision) != (state.id, state.state_version, state.epoch, revision):
            raise ScenarioError(409, "Original rescue plan does not match the frozen study snapshot.")
        snapshot = state.model_dump(mode="json")
        snapshot_sha = hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        plan_identity = original.model_dump(mode="json")
        for volatile in ("plan_id", "generated_at", "timings_ms"):
            plan_identity.pop(volatile, None)
        canonical = {"snapshot": snapshot_sha, "revision": revision,
                     "plan": plan_identity, "request": request.model_dump(mode="json"),
                     "available_units": sorted(available_ids), "reserved_units": sorted(reserved_ids),
                     "resource_positions": resource_positions or {},
                     "algorithm": ROBUSTNESS_ALGORITHM_VERSION}
        key = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with self._lock, sqlite3.connect(self.path, timeout=10) as db:
            row = db.execute("SELECT record_json FROM robustness_studies WHERE idempotency_key=?", (key,)).fetchone()
            if row:
                return RobustnessStudy.model_validate_json(row[0])
            study_id = uuid.uuid4().hex
            now = datetime.now(timezone.utc).isoformat()
            record = RobustnessStudy(study_id=study_id, scenario_id=state.id, scenario_epoch=state.epoch,
                simulation_state_version=state.state_version, infrastructure_revision=revision,
                simulation_tick=state.tick, seed=state.seed, original_plan_id=original.plan_id,
                snapshot_sha256=snapshot_sha, frozen_available_unit_ids=sorted(available_ids),
            frozen_reserved_unit_ids=sorted(reserved_ids), frozen_resource_positions=resource_positions or {}, baseline=baseline,
                conditions=request.conditions, evaluation_horizon_ticks=request.evaluation_horizon_ticks,
                algorithm_version=ROBUSTNESS_ALGORITHM_VERSION, status="pending", created_at_utc=now,
                reproduction={"idempotency_sha256": key, "snapshot_sha256": snapshot_sha,
                    "seed": state.seed, "tick": state.tick, "epoch": state.epoch,
                    "state_version": state.state_version, "infrastructure_revision": revision,
                    "physical_engine": "flood-grid-v1", "allocation_engine": "scipy-linear-sum-assignment-v1",
                    "isolation": "Dedicated experiments database; no live scenario, plan, mission, resource, closure, or agent-outbox writes."})
            db.execute("INSERT INTO robustness_studies VALUES(?,?,?,?,?,?,?,?)", (study_id,state.id,key,
                json.dumps(snapshot,separators=(",", ":")), original.model_dump_json(), request.model_dump_json(),
                record.model_dump_json(), now))
        return record

    def inputs(self, study_id: str):
        with sqlite3.connect(self.path, timeout=10) as db:
            row = db.execute("SELECT snapshot_json,original_plan_json,request_json FROM robustness_studies WHERE study_id=?", (study_id,)).fetchone()
        if not row:
            return None
        return ScenarioState.model_validate_json(row[0]), RescuePlan.model_validate_json(row[1]), RobustnessStudyCreate.model_validate_json(row[2])

    def get(self, study_id: str):
        with sqlite3.connect(self.path, timeout=10) as db:
            row = db.execute("SELECT record_json FROM robustness_studies WHERE study_id=?", (study_id,)).fetchone()
        return RobustnessStudy.model_validate_json(row[0]) if row else None

    def list(self, scenario_id: str, limit: int = 20):
        with sqlite3.connect(self.path, timeout=10) as db:
            rows = db.execute("SELECT record_json FROM robustness_studies WHERE scenario_id=? ORDER BY created_at_utc DESC LIMIT ?", (scenario_id, max(1,min(limit,50)))).fetchall()
        return [RobustnessStudy.model_validate_json(row[0]) for row in rows]

    def update(self, study_id: str, **changes):
        with self._lock, sqlite3.connect(self.path, timeout=10) as db:
            row = db.execute("SELECT record_json FROM robustness_studies WHERE study_id=?", (study_id,)).fetchone()
            if not row:
                raise KeyError(study_id)
            data = json.loads(row[0]); data.update(changes)
            record = RobustnessStudy.model_validate(data)
            db.execute("UPDATE robustness_studies SET record_json=? WHERE study_id=?", (record.model_dump_json(), study_id))
        return record

    def mark_stale(self, study_id: str, reason: str):
        return self.update(study_id, stale=True, stale_reason=reason)


def _as_prediction_set(state: ScenarioState, mode: str):
    try:
        predictions = predict_state(state)
    except ModelUnavailable as exc:
        return None, {"status": "unavailable", "warnings": [str(exc)], "calibration_status": "unavailable"}
    status = {"status": predictions.reliability_status,
              "warnings": list(predictions.reliability_warnings),
              "calibration_status": predictions.calibration_status,
              "model_version": predictions.model_version,
              "probabilities_calibrated": predictions.probabilities_calibrated}
    if mode == "injected_unavailable":
        return None, {**status, "status": "unavailable", "failure_injection": "analytical_failure_injection",
                      "warnings": status["warnings"] + ["Model unavailability was explicitly injected for this hypothetical study."]}
    if mode == "no_forecast_destinations":
        return predictions.model_copy(update={"predictions": []}), {
            **status, "status": "degraded", "failure_injection": "forecast_eligibility_suppressed",
            "warnings": status["warnings"] + ["Forecast-only destination eligibility was suppressed for this analytical condition; physical exposure remains active."]}
    if mode == "outside_support":
        supported = [p for p in predictions.predictions if p.distribution_support_status in ("within_observed_support", "edge_of_observed_support")]
        unsupported = len(predictions.predictions) - len(supported)
        # Existing eligibility policy uses only supported predictions. The status makes this intervention explicit.
        return predictions.model_copy(update={"predictions": supported}), {
            **status, "status": "degraded", "failure_injection": "unsupported_outputs_excluded_by_policy",
            "unsupported_prediction_count": unsupported,
            "warnings": status["warnings"] + [f"{unsupported} predictions outside observed support were excluded under the existing policy."]}
    return predictions, status


def _metrics(plan, priority_map=None):
    optimized = plan.comparison["optimized"]
    priorities = priority_map or {row["building_id"]: row["priority_score"] for row in plan.priorities}
    assigned = {mission["destination_id"] for mission in plan.missions}
    reached = {entry["destination_id"] for entry in plan.available_assignments}
    return {"reachable_priority_destinations": len(reached), "assigned_destinations": len(assigned),
        "priority_weighted_coverage": optimized["priority_weighted_coverage"],
        "coverage_denominator_priority_points": round(sum(priorities.values()), 2),
        "total_assigned_route_distance_m": optimized["total_distance_m"],
        "maximum_synthetic_arrival_minutes": optimized["maximum_estimated_arrival_minutes"],
        "sum_synthetic_travel_minutes": optimized["total_simulated_travel_minutes"],
        "resource_utilization": optimized["resource_utilization"],
        "unserved_destinations": max(0, len(plan.priorities) - len(assigned)),
        "objective_value": optimized["objective_value"]}


class RobustnessRunner:
    def __init__(self, repository: RobustnessRepository):
        self.repository = repository
        self._worker_lock = Lock()

    @staticmethod
    def _variant_state(base: ScenarioState, condition: Counterfactual, horizon: int) -> ScenarioState:
        changed = {key: value for key, value in {
            "rainfall_mm_h": condition.rainfall_mm_h,
            "river_level_m": condition.river_level_m,
            "drainage_effectiveness": condition.drainage_effectiveness,
        }.items() if value is not None}
        parameter_values = {**base.parameters.model_dump(), **changed}
        params = FloodSimulationParameters(**parameter_values)
        scenario_params = ScenarioParameters.model_validate(parameter_values)
        depth = np.asarray(base.depth_m, dtype=np.float64)
        balance = base.mass_balance.model_dump()
        for _ in range(horizon):
            depth, delta = step(depth, base.seed, params)
            for key in ("rainfall_m3", "river_in_m3", "river_out_m3", "drainage_m3"):
                balance[key] += delta[key]
            balance["stored_m3"] = float(depth.sum() * base.cell_size_m**2)
            balance["balance_error_m3"] = balance["stored_m3"] - (balance["initial_m3"] + balance["rainfall_m3"] + balance["river_in_m3"] - balance["river_out_m3"] - balance["drainage_m3"])
        tick = base.tick + horizon
        city = generate_city(base.seed)
        impacts = ImpactAssessment.model_validate(impact_assessment(city, depth, base.seed, params.river_level_m))
        land_depth = depth[~channel_mask()]
        return base.model_copy(update={"tick": tick, "simulated_seconds": tick * 300,
            "state_version": base.state_version + horizon, "parameters": scenario_params,
            "depth_m": depth.round(4).tolist(), "impacts": impacts,
            "maximum_depth_m": round(float(land_depth.max()) if land_depth.size else 0.0, 4),
            "affected_buildings": sum(item.water_reaches_building for item in impacts.buildings),
            "exposed_roads": sum(item.status in ("caution", "flooded") for item in impacts.roads),
            "closed_bridges": sum(item.status == "closed" for item in impacts.bridges),
            "mass_balance": MassBalance.model_validate(balance)})

    @staticmethod
    def _closure_roads(city, condition: Counterfactual):
        road_ids = {road.id for road in city.roads}
        bridge_to_road = {bridge.id: bridge.road_id for bridge in city.bridges}
        requested = set(condition.closed_asset_ids)
        known = road_ids | set(bridge_to_road)
        unknown = requested - known
        if unknown:
            raise ValueError("Unknown infrastructure asset ID(s): " + ", ".join(sorted(unknown)))
        # The existing graph can close a road directly. A bridge-only
        # intervention is applied to the corresponding bridge impact below,
        # which blocks only the graph's bridge span.
        return requested & road_ids

    @staticmethod
    def _apply_bridge_closures(state: ScenarioState, city, condition: Counterfactual):
        if condition.category != "bridge_closure":
            return state
        bridge_ids = {bridge.id for bridge in city.bridges}
        requested = set(condition.closed_asset_ids)
        unknown = requested - bridge_ids
        if unknown:
            raise ValueError("Unknown bridge ID(s): " + ", ".join(sorted(unknown)))
        impacts = state.impacts.model_copy(update={"bridges": [
            item.model_copy(update={"status": "closed"}) if item.entity_id in requested else item
            for item in state.impacts.bridges]})
        return state.model_copy(update={"impacts": impacts,
            "closed_bridges": sum(item.status == "closed" for item in impacts.bridges)})

    @staticmethod
    def _resource_set(city, unavailable_ids, unavailable_type, unavailable_count):
        units = [unit for unit in city.rescue_units if unit.status == "standby" and unit.type != "boat"]
        remove = set(unavailable_ids)
        if unavailable_type and unavailable_count:
            typed = sorted(unit.id for unit in units if unit.type == unavailable_type and unit.id not in remove)
            remove.update(typed[:unavailable_count])
        unknown = remove - {unit.id for unit in units}
        if unknown:
            raise ValueError("Unavailable resource ID(s) are not in the frozen standby inventory: " + ", ".join(sorted(unknown)))
        return city.model_copy(update={"rescue_units": [unit for unit in city.rescue_units if unit.id not in remove]}), sorted(remove)

    @staticmethod
    def _position_city(city, positions):
        if not positions:
            return city
        from .schemas import Position
        units = [unit.model_copy(update={"position": Position.model_validate(positions[unit.id])})
                 if unit.id in positions else unit for unit in city.rescue_units]
        return city.model_copy(update={"rescue_units": units})

    @staticmethod
    def _original_feasibility(original, state, city, closures, unavailable, reservations):
        graph = build_road_graph(city, state, closures)
        edge_status = {data["edge_id"]: data["status"] for _, _, data in graph.edges(data=True)}
        unit_map = {unit.id: unit for unit in city.rescue_units}
        out = []
        for mission in original.missions:
            unit_id, destination_id = mission["unit_id"], mission["destination_id"]
            unit = unit_map.get(unit_id)
            reasons = []
            if not unit or unit.status != "standby": reasons.append("Unit is not in the frozen standby inventory.")
            if unit_id in unavailable: reasons.append("Resource unavailable in this counterfactual.")
            if unit_id in reservations and unit_id not in {m["unit_id"] for m in original.missions}:
                reasons.append("Resource is reserved by another approved mission.")
            route_data = mission.get("route", {})
            invalid_edges = [edge for edge in route_data.get("edge_ids", []) if edge in edge_status and edge_status[edge] in ("closed", "flooded", "manually_blocked")]
            missing_edges = [edge for edge in route_data.get("edge_ids", []) if not edge.startswith("access:") and edge not in edge_status]
            if invalid_edges: reasons.append("Original route contains an inaccessible road or bridge segment.")
            if missing_edges: reasons.append("An original route segment is absent from the counterfactual road graph.")
            building = next((item for item in city.buildings if item.id == destination_id), None)
            if not building: reasons.append("Destination is absent from the frozen city.")
            elif unit and not any(reason.startswith("Resource unavailable") for reason in reasons):
                checked = route(graph, unit.position, building.position, unit.type)
                if not checked["reachable"]: reasons.append(checked.get("reason", "Destination is not currently reachable."))
            out.append({"unit_id": unit_id, "destination_id": destination_id,
                "original_route_feasible": not reasons, "failure_reasons": reasons,
                "original_route_edge_ids": route_data.get("edge_ids", []),
                "replacement_route_exists": bool(unit and building and route(graph, unit.position, building.position, unit.type).get("reachable"))})
        return out

    def run(self, study_id: str):
        if not self._worker_lock.acquire(blocking=False):
            current = self.repository.get(study_id)
            if current and current.status == "running":
                return
            if current and current.status == "pending":
                self.repository.update(study_id,status="failed",completed_at_utc=datetime.now(timezone.utc).isoformat(),
                    error="Another bounded robustness worker is running; retry this saved study with a new request.")
            return
        try:
            self._run_locked(study_id)
        finally:
            self._worker_lock.release()

    def _run_locked(self, study_id: str):
        record = self.repository.get(study_id)
        values = self.repository.inputs(study_id)
        if not record or not values or record.status != "pending": return
        base, original, request = values
        self.repository.update(study_id, status="running")
        started = time.perf_counter()
        city = self._position_city(generate_city(base.seed), record.frozen_resource_positions)
        frozen_reserved = set(record.frozen_reserved_unit_ids)
        baseline_plan = original
        results = []
        try:
            for condition in request.conditions:
                variant_started = time.perf_counter()
                state = self._variant_state(base, condition, request.evaluation_horizon_ticks)
                state = self._apply_bridge_closures(state, city, condition)
                closed_roads = self._closure_roads(city, condition) if condition.category in ("road_closure", "bridge_closure") else []
                variant_city, removed = self._resource_set(city, condition.unavailable_unit_ids,
                    condition.unavailable_unit_type, condition.unavailable_count)
                unavailable = set(removed)
                predictions, reliability = _as_prediction_set(state, condition.reliability_mode if condition.category == "ml_reliability" else "actual")
                if condition.category == "ml_reliability" and condition.reliability_mode in ("injected_unavailable", "no_forecast_destinations"):
                    if condition.reliability_mode == "injected_unavailable": predictions = None
                original_feasibility = self._original_feasibility(original, state, city, closed_roads, unavailable, frozen_reserved)
                feasible_original = sum(row["original_route_feasible"] for row in original_feasibility)
                active_reservations = frozen_reserved - {m["unit_id"] for m in original.missions}
                proposed = generate_plan(variant_city, state, predictions, closed_roads,
                    infrastructure_revision=record.infrastructure_revision,
                    reserved_unit_ids=active_reservations)
                # The algorithm's returned plan ID is analytical only; it is never saved in live rescue plans.
                original_ids = {(m["unit_id"], m["destination_id"]) for m in original.missions}
                optimized_ids = {(m["unit_id"], m["destination_id"]) for m in proposed.missions}
                old_destination_by_unit = {unit_id: destination_id for unit_id, destination_id in original_ids}
                new_destination_by_unit = {unit_id: destination_id for unit_id, destination_id in optimized_ids}
                changed_assignments = sum(new_destination_by_unit.get(unit_id) != destination_id
                                          for unit_id, destination_id in old_destination_by_unit.items())
                changed_assignments += sum(unit_id not in old_destination_by_unit for unit_id in new_destination_by_unit)
                results.append({"condition": condition.model_dump(mode="json"),
                    "original_plan_feasibility": {"feasible_assignments": feasible_original,
                        "total_original_assignments": len(original_feasibility), "assignments": original_feasibility,
                        "invalidated_routes": sum(not row["original_route_feasible"] for row in original_feasibility),
                        "original_assignment_stability_count": len(original_ids & optimized_ids)},
                    "reoptimized_plan": {"status": proposed.solver_status, "objective": proposed.objective,
                        "metrics": _metrics(proposed), "missions": proposed.missions,
                        "unreachable": proposed.unreachable,
                        "reassigned_units": changed_assignments,
                        "unserved_destinations": len(proposed.unreachable),
                        "manual_closure_road_ids": sorted(closed_roads)},
                    "reliability": reliability,
                    "resource_availability": {"available_unit_ids": sorted(u.id for u in variant_city.rescue_units if u.type != "boat"),
                        "unavailable_unit_ids": removed, "reserved_unit_ids_excluded": sorted(active_reservations)},
                    "timing_ms": {"condition_total": round((time.perf_counter()-variant_started)*1000,3),
                        "routing_and_assignment": proposed.timings_ms}})

            # Dependency ranking is based on closing every road present in the
            # original assignments and measuring the same planner's outcome.
            dependencies = {}
            candidate_assets = sorted({road for mission in baseline_plan.missions for road in mission.get("route", {}).get("road_ids", [])})
            candidate_assets += sorted(bridge.id for bridge in city.bridges if bridge.road_id in candidate_assets)
            base_predictions, _ = _as_prediction_set(base, "actual")
            for asset_id in candidate_assets:
                if asset_id in {bridge.id for bridge in city.bridges}:
                    perturbation = Counterfactual(condition_id=f"critical-{asset_id}", label=f"Close {asset_id}", category="bridge_closure", closed_asset_ids=[asset_id])
                    altered_state = self._apply_bridge_closures(base, city, perturbation)
                    altered_closures = []
                else:
                    altered_state = base
                    altered_closures = [asset_id]
                altered = generate_plan(city, altered_state, base_predictions, altered_closures,
                    infrastructure_revision=record.infrastructure_revision,
                    reserved_unit_ids=frozen_reserved - {m["unit_id"] for m in original.missions})
                affected = [mission for mission in original.missions if asset_id in mission.get("route", {}).get("road_ids", []) or asset_id in {bridge.id for bridge in city.bridges if bridge.road_id in mission.get("route", {}).get("road_ids", [])}]
                dependencies[asset_id] = {"asset_id": asset_id, "dependent_assignments": len(affected),
                    "affected_priority_weighted_coverage": round(sum(next((p["priority_score"] for p in original.priorities if p["building_id"] == m["destination_id"]), 0) for m in affected),2),
                    "feasible_after_closure": any(m["destination_id"] in {x["destination_id"] for x in altered.missions} for m in affected),
                    "alternate_route_assignments": [m for m in altered.missions if m["destination_id"] in {x["destination_id"] for x in affected}],
                    "optimized_priority_weighted_coverage_after_closure": altered.comparison["optimized"]["priority_weighted_coverage"]}
            ranked_dependencies = sorted(dependencies.values(), key=lambda d: (-d["dependent_assignments"], -d["affected_priority_weighted_coverage"], d["asset_id"]))
            baseline_summary = {"metrics": _metrics(baseline_plan), "missions": baseline_plan.missions,
                "solver_status": baseline_plan.solver_status, "objective": baseline_plan.objective}
            contingencies = []
            for result in results:
                for mission in result["reoptimized_plan"]["missions"]:
                    contingency_id = result["condition"]["condition_id"]
                    if (mission["unit_id"], mission["destination_id"]) not in {
                        (old["unit_id"], old["destination_id"]) for old in original.missions
                    }:
                        contingencies.append({"contingency_id": f"{contingency_id}:{mission['unit_id']}:{mission['destination_id']}",
                            "trigger_condition": result["condition"]["label"], "source_condition_id": contingency_id,
                            "unit_id": mission["unit_id"], "destination_id": mission["destination_id"],
                            "route": mission["route"], "resource_requirements": {"unit_type": mission["unit_type"], "capacity": mission["unit_capacity"]},
                            "synthetic_tradeoff": {"travel_minutes": mission["route"]["simulated_minutes"], "distance_m": mission["route"]["distance_m"]},
                            "coverage_after_reoptimization": result["reoptimized_plan"]["metrics"]["priority_weighted_coverage"],
                            "supporting_evidence": result["original_plan_feasibility"],
                            "review_required": True, "applied_to_live_operations": False})
            output = {"conditions": results, "critical_infrastructure": ranked_dependencies,
                "contingencies": contingencies,
                "baseline": baseline_summary,
                "interpretation": "Conditions are deterministic analytical cases, not probability-weighted forecasts. Original-route feasibility and counterfactual reoptimization are reported separately. Coverage is the sum of existing priority scores times the assigned occupant-capacity fraction; denominator is the sum of the condition-specific eligible destination priority scores.",
                "study_runtime_ms": round((time.perf_counter()-started)*1000,3)}
            self.repository.update(study_id, status="completed", completed_at_utc=datetime.now(timezone.utc).isoformat(), results=output)
        except Exception as exc:
            self.repository.update(study_id, status="failed", completed_at_utc=datetime.now(timezone.utc).isoformat(), error=f"{type(exc).__name__}: {exc}")


def read_infrastructure(path: str | Path, scenario_id: str, epoch: int):
    """Read-only lookup; a robustness study must not initialize live infra rows."""
    try:
        with sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True, timeout=5) as db:
            row = db.execute("SELECT revision FROM scenario_infrastructure WHERE scenario_id=? AND epoch=?", (scenario_id,epoch)).fetchone()
            closures = [item[0] for item in db.execute("SELECT road_id FROM road_closures WHERE scenario_id=? AND epoch=? AND active=1 ORDER BY road_id", (scenario_id,epoch))]
        return (row[0] if row else 0), closures
    except sqlite3.OperationalError:
        return 0, []


def read_reserved_units(path: str | Path, scenario_id: str, epoch: int):
    try:
        with sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True, timeout=5) as db:
            return sorted(row[0] for row in db.execute("SELECT unit_id FROM unit_resources WHERE scenario_id=? AND scenario_epoch=? AND status!='available'", (scenario_id,epoch)))
    except sqlite3.OperationalError:
        return []


def read_resource_positions(path: str | Path, scenario_id: str, epoch: int):
    try:
        with sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True, timeout=5) as db:
            rows = db.execute("SELECT unit_id,position_json FROM unit_resources WHERE scenario_id=? AND scenario_epoch=?", (scenario_id,epoch)).fetchall()
        return {unit_id: json.loads(position_json) for unit_id,position_json in rows}
    except sqlite3.OperationalError:
        return {}
