import sqlite3
from types import SimpleNamespace

import numpy as np
import pytest

from app.experiments import ExperimentCreate, ExperimentRepository, ExperimentRunner, ExperimentVariant
from app.rescue import PlanStore
from app.scenarios import ScenarioError, ScenarioStore
from app.schemas import ScenarioCreate


def _setup(path, *, preset="mild"):
    scenarios = ScenarioStore(path)
    state = scenarios.create(ScenarioCreate(name="Experiment base", seed=2026, preset=preset), "experiment-base-key").state
    repository = ExperimentRepository(path.with_name("experiments.sqlite3"))
    return scenarios, state, repository, ExperimentRunner(repository)


def _request(state, ticks=2, *, a=None, b=None):
    return ExperimentCreate(name="Repeatable A/B", base_scenario_id=state.id,
        expected_state_version=state.state_version, simulation_ticks=ticks,
        variants=[a or ExperimentVariant(variant_id="A", label="Variant A"),
                  b or ExperimentVariant(variant_id="B", label="Variant B")])


def _run(repository, runner, request, state):
    record = repository.create(request, state)
    runner.run(record.experiment_id)
    complete = repository.get(record.experiment_id)
    assert complete and complete.status == "completed", complete.error if complete else "missing experiment"
    return complete


def test_experiment_variants_are_deterministic_and_do_not_touch_live_scenario(tmp_path, monkeypatch):
    path = tmp_path / "experiments.sqlite3"
    scenarios, base, repository, runner = _setup(path)
    fake_predictions = SimpleNamespace(predictions=[], model_version="test-local")
    monkeypatch.setattr("app.experiments.predict_state", lambda _state: fake_predictions)
    before = scenarios.get(base.id).state
    with sqlite3.connect(path) as db:
        live_events_before = db.execute("SELECT count(*) FROM events WHERE scenario_id=?", (base.id,)).fetchone()[0]
        outbox_before = db.execute("SELECT count(*) FROM agent_event_outbox WHERE scenario_id=?", (base.id,)).fetchone()[0]

    first = _run(repository, runner, _request(base), base)
    second = _run(repository, runner, _request(base), base)
    one, two = first.results["variants"], second.results["variants"]
    for left, right in zip(one, two):
        assert np.array_equal(left["final_state"]["depth_m"], right["final_state"]["depth_m"])
        assert left["summary"] == right["summary"]
        assert left["time_series"] == right["time_series"]
        assert left["route_comparison"] == right["route_comparison"]

    after = scenarios.get(base.id).state
    assert after.state_version == before.state_version
    assert after.depth_m == before.depth_m
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM events WHERE scenario_id=?", (base.id,)).fetchone()[0] == live_events_before
        assert db.execute("SELECT count(*) FROM agent_event_outbox WHERE scenario_id=?", (base.id,)).fetchone()[0] == outbox_before
        assert db.execute("SELECT count(*) FROM rescue_plans WHERE scenario_id=?", (base.id,)).fetchone()[0] == 0

    restored = ExperimentRepository(path.with_name("experiments.sqlite3")).get(first.experiment_id)
    assert restored and restored.results["comparison"] == first.results["comparison"]


def test_resource_only_variation_reuses_identical_physical_series(tmp_path, monkeypatch):
    path = tmp_path / "resource-only.sqlite3"
    scenarios, base, repository, runner = _setup(path, preset="extreme")
    monkeypatch.setattr("app.experiments.predict_state", lambda _state: SimpleNamespace(predictions=[], model_version="test-local"))
    request = _request(base, ticks=3,
        a=ExperimentVariant(variant_id="A", label="Four units", available_ambulances=2, available_ground_teams=2),
        b=ExperimentVariant(variant_id="B", label="Two units", available_ambulances=1, available_ground_teams=1))
    result = _run(repository, runner, request, base)
    a, b = result.results["variants"]
    assert a["time_series"] == b["time_series"]
    assert a["final_state"]["depth_m"] == b["final_state"]["depth_m"]
    assert a["resource_availability"]["available_unit_count"] == 4
    assert b["resource_availability"]["available_unit_count"] == 2
    assert a["resource_availability"]["reserved_unit_count"] == b["resource_availability"]["reserved_unit_count"] == 0
    assert "baseline" in a["route_comparison"] and "optimized" in a["route_comparison"]
    assert a["route_comparison"]["baseline"]["available_unit_count"] == 4
    assert a["route_comparison"]["optimized"]["available_unit_count"] == 4


def test_rainfall_variation_changes_physics_and_reports_measured_delta(tmp_path, monkeypatch):
    path = tmp_path / "rainfall.sqlite3"
    scenarios, base, repository, runner = _setup(path)
    monkeypatch.setattr("app.experiments.predict_state", lambda _state: SimpleNamespace(predictions=[], model_version="test-local"))
    request = _request(base, ticks=24,
        a=ExperimentVariant(variant_id="A", label="Low rainfall", rainfall_mm_h=0, river_level_m=-1.2, drainage_effectiveness=1),
        b=ExperimentVariant(variant_id="B", label="Severe rainfall", rainfall_mm_h=300, river_level_m=5, drainage_effectiveness=0))
    result = _run(repository, runner, request, base)
    a, b = result.results["variants"]
    assert a["final_state"]["depth_m"] != b["final_state"]["depth_m"]
    assert result.results["comparison"]["deltas"]["maximum_flood_depth_m"]["absolute_b_minus_a"] != 0
    if a["summary"]["flood_affected_buildings"] != b["summary"]["flood_affected_buildings"]:
        assert result.results["comparison"]["explanations"]


def test_road_closure_uses_existing_graph_and_changes_route_without_flood_change(tmp_path, monkeypatch):
    path = tmp_path / "road-closure.sqlite3"
    _, base, repository, runner = _setup(path)
    city_buildings = __import__("app.city_service", fromlist=["generate_city"]).generate_city(base.seed).buildings
    future = [SimpleNamespace(building_id=building.id, predicted_future_exposed=True, uncalibrated_model_score=0.8)
              for building in city_buildings[:8]]
    monkeypatch.setattr("app.experiments.predict_state", lambda _state: SimpleNamespace(predictions=future, model_version="test-local"))
    request = _request(base, ticks=0,
        a=ExperimentVariant(variant_id="A", label="Road open"),
        b=ExperimentVariant(variant_id="B", label="Road closed", closed_road_ids=["road-ew-1"]))
    result = _run(repository, runner, request, base)
    a, b = result.results["variants"]
    assert a["final_state"]["depth_m"] == b["final_state"]["depth_m"]
    route_a = next(row["route"] for row in a["reachable_assignments"] if row["unit_id"] == "unit-1" and row["destination_id"] == "building-0-0-0")
    route_b = next(row["route"] for row in b["reachable_assignments"] if row["unit_id"] == "unit-1" and row["destination_id"] == "building-0-0-0")
    assert "road-ew-1" in route_a["road_ids"]
    assert "road-ew-1" not in route_b["road_ids"]
    assert route_a["road_ids"] != route_b["road_ids"]
    assert b["manual_closure_road_ids"] == ["road-ew-1"]


def test_stale_base_and_invalid_inputs_are_rejected(tmp_path):
    path = tmp_path / "validation.sqlite3"
    scenarios, base, repository, _ = _setup(path)
    updated = scenarios.update_parameters(base.id, __import__("app.schemas", fromlist=["ParameterUpdate"]).ParameterUpdate(rainfall_mm_h=12, expected_version=base.state_version)).state
    with pytest.raises(ScenarioError, match="changed"):
        repository.create(_request(base), updated)
    with pytest.raises(ValueError, match="exactly one"):
        ExperimentCreate(name="bad", base_scenario_id=base.id, expected_state_version=base.state_version,
            variants=[ExperimentVariant(variant_id="A", label="A"), ExperimentVariant(variant_id="A", label="duplicate")])


def test_cancel_pending_experiment_persists_cancelled_state(tmp_path):
    path = tmp_path / "cancel.sqlite3"
    _, base, repository, runner = _setup(path)
    record = repository.create(_request(base), base)
    cancelled = repository.cancel(record.experiment_id)
    assert cancelled and cancelled.status == "cancelled"
    runner.run(record.experiment_id)
    assert repository.get(record.experiment_id).status == "cancelled"


def test_experiment_api_persists_results_without_mutating_operational_scenario(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main

    path = tmp_path / "operational.sqlite3"
    scenarios, base, repository, runner = _setup(path)
    monkeypatch.setattr(main, "store", scenarios)
    monkeypatch.setattr(main, "experiment_repository", repository)
    monkeypatch.setattr(main, "experiment_runner", runner)
    monkeypatch.setattr("app.experiments.predict_state", lambda _state: SimpleNamespace(predictions=[], model_version="test-local"))
    before = scenarios.get(base.id).state
    with sqlite3.connect(path) as db:
        outbox_before = db.execute("SELECT count(*) FROM agent_event_outbox WHERE scenario_id=?", (base.id,)).fetchone()[0]
    body = _request(base, ticks=0).model_dump(mode="json")

    with TestClient(main.app) as client:
        created = client.post(f"/api/v1/scenarios/{base.id}/experiments", json=body)
        assert created.status_code == 202
        record = created.json()
        assert record["status"] == "pending"
        runner.run(record["experiment_id"])
        record = client.get(f"/api/v1/scenario-experiments/{record['experiment_id']}").json()
        assert record["status"] == "completed"
        assert record["results"]["variants"][0]["time_series"]
        assert client.get(f"/api/v1/scenarios/{base.id}/experiments").json()[0]["experiment_id"] == record["experiment_id"]
        assert client.get(f"/api/v1/scenario-experiments/{record['experiment_id']}").json()["status"] == "completed"

    after = scenarios.get(base.id).state
    assert after.state_version == before.state_version
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM agent_event_outbox WHERE scenario_id=?", (base.id,)).fetchone()[0] == outbox_before
        plan_table = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='rescue_plans'").fetchone()
        assert plan_table is None
