"""Isolated, reproducible A/B scenario experiments."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .city_service import generate_city
from .ml_service import ModelUnavailable, predict_state
from .rescue import PlanStore, generate_plan
from .scenarios import PRESETS, ScenarioError, ScenarioStore
from .schemas import ScenarioState

MAX_EXPERIMENT_TICKS = 120
EXPERIMENT_ENGINE_VERSION = "flood-grid-v1"
ALLOCATION_ENGINE_VERSION = "scipy-linear-sum-assignment-v1"


@contextmanager
def _experiment_database(path: str | Path):
    """Keep analytical scenario rows in the dedicated experiment database."""
    yield Path(path)


class ExperimentVariant(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    variant_id: Literal["A", "B"]
    label: str = Field(min_length=1, max_length=60)
    preset: Literal["mild", "heavy", "extreme"] | None = None
    rainfall_mm_h: float | None = Field(default=None, ge=0, le=300)
    river_level_m: float | None = Field(default=None, ge=-2, le=5)
    drainage_effectiveness: float | None = Field(default=None, ge=0, le=1)
    available_ambulances: int = Field(default=2, ge=0, le=2)
    available_ground_teams: int = Field(default=2, ge=0, le=2)
    closed_road_ids: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def unique_closures(self):
        if len(set(self.closed_road_ids)) != len(self.closed_road_ids):
            raise ValueError("A road may be listed only once per variant.")
        return self


class ExperimentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    base_scenario_id: str = Field(min_length=1, max_length=128)
    expected_state_version: int = Field(ge=1)
    simulation_ticks: int = Field(default=6, ge=0, le=MAX_EXPERIMENT_TICKS)
    variants: list[ExperimentVariant] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def require_a_and_b(self):
        if {variant.variant_id for variant in self.variants} != {"A", "B"}:
            raise ValueError("An experiment requires exactly one Variant A and one Variant B.")
        return self


class ExperimentRecord(BaseModel):
    experiment_id: str
    name: str
    base_scenario_id: str
    base_seed: int
    base_tick: int
    base_state_version: int
    base_epoch: int
    base_snapshot_ref: str
    simulation_ticks: int
    variants: list[ExperimentVariant]
    status: Literal["pending", "running", "completed", "failed", "cancel_requested", "cancelled", "interrupted"]
    progress_percent: float
    current_variant: str | None = None
    created_at_utc: str
    completed_at_utc: str | None = None
    error: str | None = None
    results: dict | None = None
    reproduction: dict


class ExperimentRepository:
    def __init__(self, db_path: str | Path):
        self.path = str(db_path)
        self._lock = Lock()
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS scenario_experiments (
                experiment_id TEXT PRIMARY KEY, base_scenario_id TEXT NOT NULL,
                base_state_json TEXT NOT NULL, request_json TEXT NOT NULL,
                record_json TEXT NOT NULL, cancel_requested INTEGER NOT NULL DEFAULT 0,
                created_at_utc TEXT NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS experiments_by_scenario ON scenario_experiments(base_scenario_id,created_at_utc DESC)")
            # A process cannot resume an in-memory worker after restart. Preserve
            # the durable record and label it honestly for explicit retry.
            rows = db.execute("SELECT experiment_id,record_json FROM scenario_experiments").fetchall()
            for experiment_id, record_json in rows:
                record = json.loads(record_json)
                if record.get("status") in ("pending", "running", "cancel_requested"):
                    record["status"] = "interrupted"
                    record["error"] = "The local service restarted before this experiment completed. Its saved baseline is available; start a new run to recompute."
                    db.execute("UPDATE scenario_experiments SET record_json=? WHERE experiment_id=?", (json.dumps(record), experiment_id))

    def create(self, request: ExperimentCreate, state: ScenarioState) -> ExperimentRecord:
        if state.id != request.base_scenario_id:
            raise ScenarioError(404, "Base scenario does not exist.")
        if state.state_version != request.expected_state_version:
            raise ScenarioError(409, f"Base scenario changed; current version is {state.state_version}.")
        city = generate_city(state.seed)
        valid_roads = {road.id for road in city.roads}
        for variant in request.variants:
            unknown = set(variant.closed_road_ids) - valid_roads
            if unknown:
                raise ScenarioError(422, "Unknown road IDs: " + ", ".join(sorted(unknown)))
        snapshot_json = state.model_dump_json()
        snapshot_hash = hashlib.sha256(json.dumps(state.model_dump(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        experiment_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        record = ExperimentRecord(
            experiment_id=experiment_id, name=request.name, base_scenario_id=state.id,
            base_seed=state.seed, base_tick=state.tick, base_state_version=state.state_version,
            base_epoch=state.epoch, base_snapshot_ref=f"sha256:{snapshot_hash}",
            simulation_ticks=request.simulation_ticks, variants=request.variants, status="pending",
            progress_percent=0, created_at_utc=now,
            reproduction={"starting_snapshot_sha256": snapshot_hash,
                "starting_parameters": state.parameters.model_dump(), "same_seed_for_both_variants": True,
                "same_base_snapshot_for_both_variants": True,
                "physical_engine": EXPERIMENT_ENGINE_VERSION,
                "allocation_engine": ALLOCATION_ENGINE_VERSION,
                "duration_seconds": request.simulation_ticks * 300,
                "time_step_seconds": 300,
                "note": "Each variant starts from the exact saved depth and mass-balance snapshot. Experiment resources, closures, events, plans, and agent outbox are isolated from the operational scenario."},
        )
        with self._lock, sqlite3.connect(self.path, timeout=10) as db:
            db.execute("INSERT INTO scenario_experiments VALUES(?,?,?,?,?,?,?)", (
                experiment_id, state.id, snapshot_json, request.model_dump_json(),
                record.model_dump_json(), 0, now))
        return record

    def get(self, experiment_id: str) -> ExperimentRecord | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT record_json FROM scenario_experiments WHERE experiment_id=?", (experiment_id,)).fetchone()
        return ExperimentRecord.model_validate_json(row[0]) if row else None

    def list(self, scenario_id: str, limit: int = 20) -> list[ExperimentRecord]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT record_json FROM scenario_experiments WHERE base_scenario_id=? ORDER BY created_at_utc DESC LIMIT ?", (scenario_id, limit)).fetchall()
        return [ExperimentRecord.model_validate_json(row[0]) for row in rows]

    def inputs(self, experiment_id: str):
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT base_state_json,request_json FROM scenario_experiments WHERE experiment_id=?", (experiment_id,)).fetchone()
        return (ScenarioState.model_validate_json(row[0]), ExperimentCreate.model_validate_json(row[1])) if row else None

    def update(self, experiment_id: str, **changes) -> ExperimentRecord:
        with self._lock, sqlite3.connect(self.path, timeout=10) as db:
            row = db.execute("SELECT record_json FROM scenario_experiments WHERE experiment_id=?", (experiment_id,)).fetchone()
            if not row:
                raise KeyError(experiment_id)
            data = json.loads(row[0])
            data.update(changes)
            record = ExperimentRecord.model_validate(data)
            db.execute("UPDATE scenario_experiments SET record_json=? WHERE experiment_id=?", (record.model_dump_json(), experiment_id))
        return record

    def cancel(self, experiment_id: str) -> ExperimentRecord | None:
        with self._lock, sqlite3.connect(self.path, timeout=10) as db:
            row = db.execute("SELECT record_json FROM scenario_experiments WHERE experiment_id=?", (experiment_id,)).fetchone()
            if not row:
                return None
            record = json.loads(row[0])
            if record["status"] == "pending":
                record["status"] = "cancelled"
                record["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
            elif record["status"] == "running":
                record["status"] = "cancel_requested"
                db.execute("UPDATE scenario_experiments SET cancel_requested=1 WHERE experiment_id=?", (experiment_id,))
            db.execute("UPDATE scenario_experiments SET record_json=? WHERE experiment_id=?", (json.dumps(record), experiment_id))
        return ExperimentRecord.model_validate(record)

    def is_cancelled(self, experiment_id: str) -> bool:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT cancel_requested FROM scenario_experiments WHERE experiment_id=?", (experiment_id,)).fetchone()
        return bool(row and row[0])


class ExperimentRunner:
    def __init__(self, repository: ExperimentRepository):
        self.repository = repository

    @staticmethod
    def _state_metrics(state: ScenarioState) -> dict:
        return {"tick": state.tick, "simulated_minutes": round(state.simulated_seconds / 60, 1),
            "maximum_flood_depth_m": state.maximum_depth_m,
            "flood_affected_buildings": state.affected_buildings,
            "exposed_roads": state.exposed_roads, "closed_bridges": state.closed_bridges}

    def _variant(self, experiment_id: str, base: ScenarioState, request: ExperimentCreate,
                 variant: ExperimentVariant, variant_index: int) -> dict:
        started = time.perf_counter()
        with _experiment_database(self.repository.path) as db_path:
            scenarios = ScenarioStore(db_path)
            sid = f"experiment-{experiment_id}-{variant.variant_id.lower()}"
            state = scenarios.import_snapshot(base, sid).state
            params = state.parameters.model_dump()
            if variant.preset:
                params.update({key: value for key, value in PRESETS[variant.preset].items() if key != "name"})
            for key in ("rainfall_mm_h", "river_level_m", "drainage_effectiveness"):
                value = getattr(variant, key)
                if value is not None:
                    params[key] = value
            changed = {key: value for key, value in params.items() if state.parameters.model_dump()[key] != value}
            if changed:
                state = scenarios.update_parameters(sid, __import__("app.schemas", fromlist=["ParameterUpdate"]).ParameterUpdate(**changed, expected_version=state.state_version)).state

            series = [self._state_metrics(state)]
            denominator = max(2 * max(request.simulation_ticks, 1), 1)
            flood_started = time.perf_counter()
            for offset in range(1, request.simulation_ticks + 1):
                if self.repository.is_cancelled(experiment_id):
                    raise InterruptedError("Experiment cancelled by user.")
                state = scenarios.advance(sid, __import__("app.schemas", fromlist=["AdvanceRequest"]).AdvanceRequest(
                    steps=1, single_step=True, expected_version=state.state_version)).state
                series.append(self._state_metrics(state))
                progress = ((variant_index * request.simulation_ticks + offset) / denominator) * 100
                self.repository.update(experiment_id, progress_percent=round(progress, 1), current_variant=variant.variant_id)
            flood_simulation_ms = round((time.perf_counter() - flood_started) * 1000, 3)

            city = generate_city(base.seed)
            units = [unit for unit in city.rescue_units if unit.status == "standby" and (
                (unit.type == "ambulance" and variant.available_ambulances > 0) or
                (unit.type == "rescue_team" and variant.available_ground_teams > 0))]
            # Deterministically take the configured count per class.
            units = [unit for unit in units if unit.type != "ambulance"] + [
                unit for unit in city.rescue_units if unit.type == "ambulance" and unit.status == "standby"][:variant.available_ambulances]
            units = [unit for unit in units if unit.type != "rescue_team"] + [
                unit for unit in city.rescue_units if unit.type == "rescue_team" and unit.status == "standby"][:variant.available_ground_teams]
            city = city.model_copy(update={"rescue_units": units})

            plans = PlanStore(db_path)
            if variant.closed_road_ids:
                with sqlite3.connect(db_path) as db:
                    db.executemany("INSERT INTO road_closures(scenario_id,epoch,road_id,reason,active) VALUES(?,?,?,'what-if experiment',1)",
                        [(sid, state.epoch, road_id) for road_id in sorted(variant.closed_road_ids)])
                    db.execute("INSERT OR REPLACE INTO scenario_infrastructure(scenario_id,epoch,revision) VALUES(?,?,?)",
                        (sid, state.epoch, len(variant.closed_road_ids)))
            revision, closures = plans.infrastructure(sid, state.epoch)
            ml_status = "ready"
            model_version = None
            ml_started = time.perf_counter()
            try:
                prediction_set = predict_state(state)
                model_version = prediction_set.model_version
            except ModelUnavailable as exc:
                ml_status = "unavailable"
                prediction_set = type("UnavailablePredictions", (), {"predictions": []})()
                ml_error = str(exc)
            else:
                ml_error = None
            ml_inference_ms = round((time.perf_counter() - ml_started) * 1000, 3)
            plan = generate_plan(city, state, prediction_set, closures, infrastructure_revision=revision)
            priority_threshold = 70.0
            high_priority = [row for row in plan.priorities if row["priority_score"] >= priority_threshold]
            reachable_ids = {row["destination_id"] for row in plan.available_assignments}
            comparison = {name: metrics for name, metrics in plan.comparison.items() if name in ("baseline", "optimized")}
            allocation_deltas = {}
            for metric in ("destinations_covered", "priority_weighted_coverage", "occupants_targeted",
                           "total_distance_m", "total_simulated_travel_minutes",
                           "maximum_estimated_arrival_minutes", "resource_utilization",
                           "unreachable_destinations", "objective_value"):
                baseline_value = comparison["baseline"][metric]
                optimized_value = comparison["optimized"][metric]
                absolute = round(float(optimized_value) - float(baseline_value), 3)
                allocation_deltas[metric] = {"baseline": baseline_value, "optimized": optimized_value,
                    "absolute_optimized_minus_baseline": absolute,
                    "relative_percent_vs_baseline": round(absolute / abs(float(baseline_value)) * 100, 2)
                        if float(baseline_value) else None}
            results = {
                "variant_id": variant.variant_id, "label": variant.label,
                "configuration": variant.model_dump(),
                "final_state": state.model_dump(), "time_series": series,
                "summary": self._state_metrics(state),
                "high_priority_destinations": len(high_priority),
                "high_priority_threshold_score": priority_threshold,
                "reachable_rescue_destinations": len(reachable_ids),
                "reachable_destination_ids": sorted(reachable_ids),
                "unreachable_destinations": plan.unreachable,
                "reachable_assignments": plan.available_assignments,
                "resource_availability": {"ambulances": variant.available_ambulances,
                    "ground_teams": variant.available_ground_teams,
                    "available_unit_count": len(units), "reserved_unit_count": 0},
                "route_comparison": comparison,
                "optimized_vs_conventional_deltas": allocation_deltas,
                "optimized_missions": plan.missions,
                "conventional_missions": plan.comparison["baseline_missions"],
                "objective": plan.objective, "solver_status": plan.solver_status,
                "machine_learning": {"status": ml_status, "model_version": model_version,
                    "uncalibrated": ml_status == "ready", "unavailable_reason": ml_error},
                "manual_closure_road_ids": sorted(closures),
                "timings_ms": {"flood_simulation": flood_simulation_ms, "ml_inference": ml_inference_ms,
                    "routing": plan.timings_ms.get("routing", 0.0),
                    "assignment": plan.timings_ms.get("assignment", 0.0),
                    "variant_wall": round((time.perf_counter() - started) * 1000, 3)},
            }
            return results

    @staticmethod
    def _comparison(results: list[dict], variants: list[ExperimentVariant]) -> dict:
        first, second = results
        metrics = ["maximum_flood_depth_m", "flood_affected_buildings", "exposed_roads", "closed_bridges",
            "reachable_rescue_destinations", "destinations_covered", "priority_weighted_coverage",
            "occupants_targeted", "total_distance_m", "total_simulated_travel_minutes",
            "maximum_estimated_arrival_minutes", "resource_utilization", "unreachable_destinations",
            "objective_value"]
        deltas = {}
        for metric in metrics:
            if metric in first["summary"]:
                a, b = first["summary"][metric], second["summary"][metric]
            else:
                a = first["route_comparison"]["optimized"].get(metric)
                b = second["route_comparison"]["optimized"].get(metric)
            if a is None or b is None:
                continue
            absolute = round(float(b) - float(a), 3)
            deltas[metric] = {"variant_a": a, "variant_b": b, "absolute_b_minus_a": absolute,
                "relative_percent_b_vs_a": round(absolute / abs(float(a)) * 100, 2) if float(a) else None}
        explanations = []
        labels = {v.variant_id: v.label for v in variants}
        affected = deltas.get("flood_affected_buildings", {}).get("absolute_b_minus_a", 0)
        if affected:
            direction = "more" if affected > 0 else "fewer"
            explanations.append(f"After {second['summary']['simulated_minutes']:g} simulated minutes, {labels['B']} had {abs(int(affected))} {direction} buildings cross the physical exposure threshold than {labels['A']}.")
        coverage = deltas.get("priority_weighted_coverage", {}).get("absolute_b_minus_a", 0)
        if coverage:
            direction = "increased" if coverage > 0 else "decreased"
            explanations.append(f"Under the same starting snapshot and horizon, priority-weighted optimized coverage {direction} by {abs(coverage):g} score points in {labels['B']} versus {labels['A']}.")
        return {"variant_a_id": "A", "variant_b_id": "B", "deltas": deltas,
            "explanations": explanations,
            "fairness": "Both variants use the same immutable base snapshot, seed, physical engine, horizon, graph rules, priority formula, unit compatibility/capacity rules, and baseline/optimized solver inputs except for the configuration values shown for each variant."}

    def run(self, experiment_id: str) -> None:
        record = self.repository.get(experiment_id)
        inputs = self.repository.inputs(experiment_id)
        if not record or not inputs or record.status == "cancelled":
            return
        if record.status not in ("pending",):
            return
        base, request = inputs
        self.repository.update(experiment_id, status="running", error=None)
        results = []
        try:
            for index, variant in enumerate(sorted(request.variants, key=lambda item: item.variant_id)):
                self.repository.update(experiment_id, current_variant=variant.variant_id)
                results.append(self._variant(experiment_id, base, request, variant, index))
            if self.repository.is_cancelled(experiment_id):
                raise InterruptedError("Experiment cancelled by user.")
            result_data = {"variants": results, "comparison": self._comparison(results, request.variants),
                "experiment_runtime_ms": round(sum(v["timings_ms"]["variant_wall"] for v in results), 3),
                "payload_bytes": 0}
            result_data["payload_bytes"] = len(json.dumps(result_data, separators=(",", ":")).encode())
            self.repository.update(experiment_id, status="completed", progress_percent=100, current_variant=None,
                completed_at_utc=datetime.now(timezone.utc).isoformat(), results=result_data)
        except InterruptedError as exc:
            self.repository.update(experiment_id, status="cancelled", current_variant=None,
                completed_at_utc=datetime.now(timezone.utc).isoformat(), error=str(exc))
        except Exception as exc:
            self.repository.update(experiment_id, status="failed", current_variant=None,
                completed_at_utc=datetime.now(timezone.utc).isoformat(), error=f"{type(exc).__name__}: {exc}")
