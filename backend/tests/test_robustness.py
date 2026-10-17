import sqlite3
from types import SimpleNamespace

import numpy as np
import pytest

from app.city_service import generate_city
from app.experiments import ExperimentRepository
from app.rescue import PlanStore, build_road_graph, generate_plan
from app.robustness import (Counterfactual, RobustnessRepository, RobustnessRunner,
    RobustnessStudyCreate, _as_prediction_set, read_infrastructure)
from app.scenarios import ScenarioStore
from app.schemas import AdvanceRequest, ParameterUpdate, ScenarioCreate, ScenarioPredictionSet


def _fixture(tmp_path, monkeypatch):
    live_path = tmp_path / "live.sqlite3"
    scenarios = ScenarioStore(live_path)
    state = scenarios.create(ScenarioCreate(name="Frozen robustness", seed=2026, preset="heavy"), "robustness-seed-key").state
    plans = PlanStore(live_path)
    analytics = tmp_path / "experiments.sqlite3"
    ExperimentRepository(analytics)
    repository = RobustnessRepository(analytics)
    runner = RobustnessRunner(repository)
    empty_predictions = ScenarioPredictionSet(model_version="test-model", scenario_id=state.id,
        scenario_state_version=state.state_version, scenario_tick=state.tick, scenario_epoch=state.epoch,
        horizon_ticks=6, horizon_minutes=30, target_definition="synthetic test", reliability_status="available",
        calibration_status="validated_synthetic", probabilities_calibrated=True, predictions=[])
    monkeypatch.setattr("app.robustness.predict_state", lambda _state: empty_predictions)
    revision, closures = read_infrastructure(live_path, state.id, state.epoch)
    city = generate_city(state.seed)
    reserved = []
    plan = generate_plan(city, state, empty_predictions, closures, infrastructure_revision=revision)
    return live_path, scenarios, state, plans, repository, runner, city, revision, reserved, plan


def _request(state, revision, condition, *, horizon=2, plan_id=None):
    return RobustnessStudyCreate(scenario_id=state.id, expected_state_version=state.state_version,
        expected_epoch=state.epoch, expected_infrastructure_revision=revision,
        original_plan_id=plan_id, evaluation_horizon_ticks=horizon, conditions=[condition])


def test_study_is_frozen_deterministic_and_separate_from_operational_stores(tmp_path, monkeypatch):
    live_path, scenarios, state, _plans, repository, runner, city, revision, reserved, plan = _fixture(tmp_path, monkeypatch)
    condition = Counterfactual(condition_id="rain", label="Rain escalation", category="environment", rainfall_mm_h=240)
    request = _request(state, revision, condition)
    baseline = {"missions": plan.missions, "metrics": plan.comparison["optimized"]}
    available = [unit.id for unit in city.rescue_units if unit.type != "boat"]
    with sqlite3.connect(live_path) as db:
        before = {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("events", "rescue_plans", "missions", "agent_event_outbox", "road_closures", "scenario_infrastructure")}
    position_snapshot={available[0]:{"x_m":12.0,"y_m":-5.0,"elevation_m":1.2}}
    first = repository.create(request, state, revision, available, reserved, plan, baseline, position_snapshot)
    duplicate = repository.create(request, state, revision, available, reserved, plan, baseline, position_snapshot)
    assert first.study_id == duplicate.study_id
    assert first.frozen_resource_positions == position_snapshot
    runner.run(first.study_id)
    complete = repository.get(first.study_id)
    assert complete and complete.status == "completed"
    assert complete.snapshot_sha256 == complete.reproduction["snapshot_sha256"]
    condition_result = complete.results["conditions"][0]
    assert condition_result["condition"]["category"] == "environment"
    assert "original_plan_feasibility" in condition_result and "reoptimized_plan" in condition_result
    assert condition_result["reoptimized_plan"]["status"] == "optimal_linear_sum_assignment"
    with sqlite3.connect(live_path) as db:
        after = {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in before}
    assert after == before
    restored = RobustnessRepository(tmp_path / "experiments.sqlite3").get(first.study_id)
    assert restored and restored.results == complete.results
    assert scenarios.get(state.id).state.state_version == state.state_version


def test_environmental_variant_uses_flood_step_and_recomputes_impacts():
    from app.robustness import RobustnessRunner
    # Reuse a state from the same deterministic store fixture without an external model.
    from app.scenarios import ScenarioStore as Store
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        state = Store(f"{folder}/state.sqlite3").create(ScenarioCreate(name="Rain", seed=2026), "rain-seed-key").state
    condition = Counterfactual(condition_id="rain", label="Rain", category="environment", rainfall_mm_h=260)
    changed = RobustnessRunner._variant_state(state, condition, 3)
    from app.flood import channel_mask
    assert np.asarray(changed.depth_m)[~channel_mask()].max() > np.asarray(state.depth_m)[~channel_mask()].max()
    assert changed.tick == state.tick + 3
    assert changed.state_version == state.state_version + 3
    assert changed.mass_balance.balance_error_m3 == pytest.approx(0, abs=0.02)


def test_bridge_closure_is_span_specific_and_resource_reduction_is_explicit(tmp_path, monkeypatch):
    _live, _scenarios, state, _plans, _repo, _runner, city, _revision, _reserved, _plan = _fixture(tmp_path, monkeypatch)
    bridge = city.bridges[0]
    condition = Counterfactual(condition_id="bridge", label="Bridge closed", category="bridge_closure", closed_asset_ids=[bridge.id])
    altered = RobustnessRunner._apply_bridge_closures(state, city, condition)
    assert any(item.entity_id == bridge.id and item.status == "closed" for item in altered.impacts.bridges)
    assert state.impacts.bridges != altered.impacts.bridges
    graph = build_road_graph(city, altered, [])
    bridge_edges = [data for _,_,data in graph.edges(data=True) if data.get("bridge_id") == bridge.id]
    non_bridge_edges = [data for _,_,data in graph.edges(data=True) if data.get("road_id") == bridge.road_id and data.get("bridge_id") != bridge.id]
    assert bridge_edges and all(edge["status"] == "closed" for edge in bridge_edges)
    assert non_bridge_edges and all(edge["status"] != "closed" for edge in non_bridge_edges)
    remaining, removed = RobustnessRunner._resource_set(city, [], "ambulance", 1)
    assert len(removed) == 1 and len(remaining.rescue_units) == len(city.rescue_units) - 1
    assert removed[0] in {unit.id for unit in city.rescue_units if unit.type == "ambulance"}


def test_original_plan_closure_failure_is_separate_from_valid_reoptimization(tmp_path, monkeypatch):
    live_path = tmp_path / "roads.sqlite3"
    scenarios = ScenarioStore(live_path)
    state = scenarios.create(ScenarioCreate(name="Flooded road test", seed=2026, preset="extreme"), "road-test-seed-key").state
    state = scenarios.update_parameters(state.id, ParameterUpdate(expected_version=state.state_version,
        rainfall_mm_h=300, river_level_m=2.5, drainage_effectiveness=0)).state
    for _ in range(12):
        state = scenarios.advance(state.id, AdvanceRequest(steps=1, single_step=True,
            expected_version=state.state_version)).state
    city = generate_city(state.seed)
    predictions = ScenarioPredictionSet(model_version="test-model", scenario_id=state.id,
        scenario_state_version=state.state_version, scenario_tick=state.tick, scenario_epoch=state.epoch,
        horizon_ticks=6, horizon_minutes=30, target_definition="synthetic test", reliability_status="available",
        calibration_status="validated_synthetic", probabilities_calibrated=True, predictions=[])
    monkeypatch.setattr("app.robustness.predict_state", lambda _state: predictions)
    plan = generate_plan(city,state,predictions)
    assert plan.missions, "the documented deterministic flood case should yield assignments"
    target = next(mission for mission in plan.missions if mission["route"]["road_ids"])
    closed_road = target["route"]["road_ids"][0]
    analytics = tmp_path / "roads-experiments.sqlite3"
    ExperimentRepository(analytics)
    repository = RobustnessRepository(analytics)
    runner = RobustnessRunner(repository)
    condition = Counterfactual(condition_id="closure",label=f"Close {closed_road}",category="road_closure",closed_asset_ids=[closed_road])
    request = _request(state,0,condition,horizon=0,plan_id=plan.plan_id)
    available = sorted(unit.id for unit in city.rescue_units if unit.status=="standby" and unit.type!="boat")
    study = repository.create(request,state,0,available,[],plan,{"missions":plan.missions})
    runner.run(study.study_id)
    result = repository.get(study.study_id)
    assert result and result.status == "completed", result.error if result else "study missing"
    condition_result = result.results["conditions"][0]
    original = next(row for row in condition_result["original_plan_feasibility"]["assignments"]
        if row["destination_id"] == target["destination_id"])
    assert original["original_route_feasible"] is False
    assert any("closed" in reason or "inaccessible" in reason for reason in original["failure_reasons"])
    graph = build_road_graph(city,state,[closed_road])
    edge_status = {data["edge_id"]:data["status"] for _,_,data in graph.edges(data=True)}
    for mission in condition_result["reoptimized_plan"]["missions"]:
        for edge_id in mission["route"]["edge_ids"]:
            if edge_id.startswith("access:"):
                continue
            assert edge_id in edge_status
            assert edge_status[edge_id] not in ("closed","flooded","manually_blocked")
    assert condition_result["reoptimized_plan"]["status"] == "optimal_linear_sum_assignment"


def test_bad_frozen_identity_and_unknown_assets_are_rejected(tmp_path, monkeypatch):
    _live, _scenarios, state, _plans, repository, _runner, city, revision, reserved, plan = _fixture(tmp_path, monkeypatch)
    condition = Counterfactual(condition_id="road", label="Unknown road", category="road_closure", closed_asset_ids=["not-a-road"])
    request = _request(state, revision, condition, plan_id=plan.plan_id)
    with pytest.raises(ValueError, match="Unknown infrastructure"):
        RobustnessRunner._closure_roads(city, condition)
    wrong_request = request.model_copy(update={"expected_state_version":state.state_version + 1})
    with pytest.raises(Exception, match="do not match"):
        repository.create(wrong_request, state, revision, [], reserved, plan, {})


def test_frozen_live_closures_survive_all_counterfactual_families_without_live_mutation(tmp_path, monkeypatch):
    live_path, scenarios, state, plans, repository, runner, city, revision, reserved, _plan = _fixture(tmp_path, monkeypatch)
    plans.infrastructure(state.id,state.epoch)
    bridge_roads={bridge.road_id for bridge in city.bridges}
    manual_road=next(road.id for road in city.roads if road.id not in bridge_roads)
    extra_road=next(road.id for road in city.roads if road.id not in bridge_roads and road.id!=manual_road)
    bridge=city.bridges[0]
    with sqlite3.connect(live_path) as db:
        db.execute("INSERT INTO road_closures(scenario_id,epoch,road_id,reason,active) VALUES(?,?,?,?,1)",
            (state.id,state.epoch,manual_road,"frozen pre-existing closure"))
        db.execute("UPDATE scenario_infrastructure SET revision=? WHERE scenario_id=? AND epoch=?",
            (revision+1,state.id,state.epoch))
    frozen_revision,live_closures=read_infrastructure(live_path,state.id,state.epoch)
    assert live_closures==[manual_road]
    predictions=ScenarioPredictionSet(model_version="test-model",scenario_id=state.id,
        scenario_state_version=state.state_version,scenario_tick=state.tick,scenario_epoch=state.epoch,
        horizon_ticks=6,horizon_minutes=30,target_definition="synthetic test",reliability_status="available",
        calibration_status="validated_synthetic",probabilities_calibrated=True,predictions=[])
    monkeypatch.setattr("app.robustness.predict_state",lambda _state:predictions)
    plan=generate_plan(city,state,predictions,live_closures,infrastructure_revision=frozen_revision)
    conditions=[
        Counterfactual(condition_id="baseline",label="Baseline",category="baseline"),
        Counterfactual(condition_id="rain",label="Environmental change",category="environment",rainfall_mm_h=240),
        Counterfactual(condition_id="resource",label="Resource loss",category="resources",unavailable_unit_type="ambulance",unavailable_count=1),
        Counterfactual(condition_id="bridge",label="Bridge closure",category="bridge_closure",closed_asset_ids=[bridge.id]),
        Counterfactual(condition_id="extra-road",label="Additional road closure",category="road_closure",closed_asset_ids=[extra_road]),
    ]
    request=RobustnessStudyCreate(scenario_id=state.id,expected_state_version=state.state_version,
        expected_epoch=state.epoch,expected_infrastructure_revision=frozen_revision,evaluation_horizon_ticks=1,
        conditions=conditions)
    available=sorted(unit.id for unit in city.rescue_units if unit.status=="standby" and unit.type!="boat")
    baseline={"missions":plan.missions,"metrics":plan.comparison["optimized"],"manual_closure_road_ids":live_closures}
    study=repository.create(request,state,frozen_revision,available,reserved,plan,baseline)
    assert study.frozen_manual_closure_road_ids==[manual_road]
    assert study.reproduction["manual_closure_road_ids"]==[manual_road]
    alternate_identity=repository.create(request,state,frozen_revision,available,reserved,plan,
        {**baseline,"manual_closure_road_ids":[]})
    assert alternate_identity.study_id!=study.study_id
    assert alternate_identity.snapshot_sha256!=study.snapshot_sha256
    with sqlite3.connect(live_path) as db:
        operational_before={
            "closure_rows":db.execute("SELECT scenario_id,epoch,road_id,reason,active FROM road_closures ORDER BY road_id").fetchall(),
            "infrastructure":db.execute("SELECT scenario_id,epoch,revision FROM scenario_infrastructure ORDER BY scenario_id,epoch").fetchall(),
        }
    runner.run(study.study_id)
    completed=repository.get(study.study_id)
    assert completed and completed.status=="completed",completed.error if completed else "missing study"
    assert completed.snapshot_sha256==completed.reproduction["snapshot_sha256"]
    assert completed.results["frozen_manual_closure_road_ids"]==[manual_road]
    for item in completed.results["conditions"]:
        condition=next(candidate for candidate in conditions if candidate.condition_id==item["condition"]["condition_id"])
        effective=set(item["effective_manual_closure_road_ids"])
        assert manual_road in effective
        expected=set(live_closures)
        if condition.category=="road_closure":expected.add(extra_road)
        assert effective==expected
        variant=runner._variant_state(state,condition,1)
        variant=runner._apply_bridge_closures(variant,city,condition)
        graph=build_road_graph(city,variant,effective)
        edge_map={data["edge_id"]:data for _,_,data in graph.edges(data=True)}
        for mission in item["reoptimized_plan"]["missions"]:
            assert manual_road not in mission["route"]["road_ids"]
            if condition.category=="road_closure":assert extra_road not in mission["route"]["road_ids"]
            for edge_id in mission["route"]["edge_ids"]:
                if edge_id.startswith("access:"):continue
                assert edge_id in edge_map
                edge=edge_map[edge_id]
                assert edge["status"] not in ("closed","flooded","manually_blocked")
                assert not (edge.get("bridge_id") and edge.get("status")=="closed")
        assert item["reoptimized_plan"]["manual_closure_road_ids"]==sorted(expected)
    for dependency in completed.results["critical_infrastructure"]:
        assert manual_road in dependency["effective_manual_closure_road_ids"]
        assert all(manual_road not in mission["route"]["road_ids"] for mission in dependency["alternate_route_assignments"])
    with sqlite3.connect(live_path) as db:
        operational_after={
            "closure_rows":db.execute("SELECT scenario_id,epoch,road_id,reason,active FROM road_closures ORDER BY road_id").fetchall(),
            "infrastructure":db.execute("SELECT scenario_id,epoch,revision FROM scenario_infrastructure ORDER BY scenario_id,epoch").fetchall(),
        }
    assert operational_after==operational_before
    assert scenarios.get(state.id).state.state_version==state.state_version


def test_missing_ml_metadata_is_reported_as_unavailable(monkeypatch):
    from app.ml_service import ModelUnavailable
    def unavailable(_state): raise ModelUnavailable("test metadata missing")
    monkeypatch.setattr("app.robustness.predict_state", unavailable)
    predictions, status = _as_prediction_set(object(), "actual")
    assert predictions is None
    assert status["status"] == "unavailable"
    assert "test metadata missing" in status["warnings"][0]


def test_api_study_creation_is_analytical_and_becomes_historical_after_change(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    live_path = tmp_path / "api-live.sqlite3"
    scenarios = ScenarioStore(live_path)
    state = scenarios.create(ScenarioCreate(name="API frozen", seed=2026), "api-study-seed-key").state
    plans = PlanStore(live_path)
    analytics = tmp_path / "api-experiments.sqlite3"
    ExperimentRepository(analytics)
    repository = RobustnessRepository(analytics)
    predictions = ScenarioPredictionSet(model_version="test-model", scenario_id=state.id,
        scenario_state_version=state.state_version, scenario_tick=state.tick, scenario_epoch=state.epoch,
        horizon_ticks=6, horizon_minutes=30, target_definition="synthetic test", reliability_status="available",
        calibration_status="validated_synthetic", probabilities_calibrated=True, predictions=[])
    monkeypatch.setattr(main,"store",scenarios)
    monkeypatch.setattr(main,"rescue_plans",plans)
    monkeypatch.setattr(main,"robustness_repository",repository)
    monkeypatch.setattr(main,"robustness_runner",RobustnessRunner(repository))
    monkeypatch.setattr(main,"predict_state",lambda _state:predictions)
    condition=Counterfactual(condition_id="model-down",label="Model unavailable",category="ml_reliability",reliability_mode="injected_unavailable")
    with TestClient(main.app) as client:
        baseline=client.get(f"/api/v1/scenarios/{state.id}/robustness-baseline").json()
        body={"scenario_id":state.id,"expected_state_version":state.state_version,"expected_epoch":state.epoch,
            "expected_infrastructure_revision":baseline["infrastructure_revision"],"evaluation_horizon_ticks":0,
            "conditions":[condition.model_dump(mode="json")]}
        response=client.post(f"/api/v1/scenarios/{state.id}/robustness-studies",json=body)
        assert response.status_code==202,response.text
        study=client.get(f"/api/v1/robustness-studies/{response.json()['study_id']}").json()
        assert study["status"]=="completed"
        assert study["results"]["conditions"][0]["reliability"]["failure_injection"]=="analytical_failure_injection"
        assert study["results"]["conditions"][0]["reoptimized_plan"]["missions"]==[]
        assert plans.latest_valid(state.id,state) is None
        plans.infrastructure(state.id,state.epoch)
        closed_road=generate_city(state.seed).roads[0].id
        with sqlite3.connect(live_path) as db:
            db.execute("INSERT INTO road_closures(scenario_id,epoch,road_id,reason,active) VALUES(?,?,?,?,1)",
                (state.id,state.epoch,closed_road,"post-study infrastructure change"))
            db.execute("UPDATE scenario_infrastructure SET revision=revision+1 WHERE scenario_id=? AND epoch=?",(state.id,state.epoch))
        stale_closure=client.get(f"/api/v1/robustness-studies/{study['study_id']}").json()
        assert stale_closure["stale"] is True
        assert "infrastructure revision changed" in stale_closure["stale_reason"]
        changed=scenarios.update_parameters(state.id,ParameterUpdate(expected_version=state.state_version,rainfall_mm_h=10)).state
        historical=client.get(f"/api/v1/robustness-studies/{study['study_id']}").json()
        assert historical["stale"] is True
        assert historical["simulation_state_version"]==state.state_version
        assert changed.state_version != historical["simulation_state_version"]
        reset=scenarios.reset(state.id,changed.state_version).state
        after_reset=client.get(f"/api/v1/robustness-studies/{study['study_id']}").json()
        assert after_reset["stale"] is True
        assert reset.epoch > after_reset["scenario_epoch"]
