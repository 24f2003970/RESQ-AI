import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.city_service import generate_city
from app.flood import CELL_AREA_M2, SimulationParameters, channel_mask, impact_assessment, initial_depth, step
from app.main import app
from app.scenarios import ScenarioError, ScenarioStore
from app.schemas import AdvanceRequest, ParameterUpdate, ScenarioCreate
from app.terrain import terrain_grid

client = TestClient(app)


def test_terrain_is_repeatable_and_lower_at_the_canal():
    first = terrain_grid(17).copy()
    assert np.array_equal(first, terrain_grid(17))
    assert first.shape == (25, 33)
    assert first[12].mean() < first[0].mean()
    assert np.ptp(first) > 1


def test_city_asset_elevations_use_the_scenario_seeded_terrain():
    city = generate_city(42)
    building = city.buildings[0]
    from app.terrain import terrain_at
    assert city.city.id == "city-v1-42"
    assert building.position.elevation_m == pytest.approx(terrain_at(building.position.x_m, building.position.y_m, 42))


def test_rainfall_increases_surface_water_and_is_deterministic():
    initial = initial_depth(2026)
    params = SimulationParameters(rainfall_mm_h=100, river_level_m=-0.8, drainage_effectiveness=0.2)
    one, one_mass = step(initial, 2026, params, steps=4)
    two, two_mass = step(initial, 2026, params, steps=4)
    assert np.array_equal(one, two)
    assert one_mass == two_mass
    assert one.min() >= 0
    assert one.sum() > initial.sum()
    assert abs(one_mass["balance_error_m3"]) < 1e-7


def test_drainage_is_bounded_and_mass_is_accounted():
    water = np.full((25, 33), 0.08)
    before = water.sum() * CELL_AREA_M2
    after, mass = step(water, 2026, SimulationParameters(drainage_effectiveness=1), steps=1)
    assert np.all(after >= 0)
    assert mass["drainage_m3"] <= before
    assert abs(mass["balance_error_m3"]) < 1e-7


def test_river_boundary_and_road_building_impacts_follow_depth():
    city = generate_city()
    baseline = impact_assessment(city, initial_depth(2026), 2026, -0.8)
    assert all(item["status"] == "open" for item in baseline["bridges"])
    assert all(item["status"] == "open" for item in baseline["roads"])
    stage_only = impact_assessment(city, initial_depth(2026, 0.25), 2026, 0.25)
    assert all(item["status"] == "open" for item in stage_only["bridges"])
    assert all(item["status"] == "open" for item in stage_only["roads"])
    depth = initial_depth(2026, 2.0)
    impact = impact_assessment(city, depth, 2026, 2.0)
    assert any(item["status"] == "closed" for item in impact["bridges"])
    building = city.buildings[0]
    ix = int(np.clip(np.floor((building.position.x_m + 330) / 20), 0, 32))
    iy = int(np.clip(np.floor((building.position.y_m + 250) / 20), 0, 24))
    depth[iy, ix] = 0.6
    impact = impact_assessment(city, depth, 2026, -0.8)
    assert next(item for item in impact["buildings"] if item["entity_id"] == building.id)["category"] in ("moderate", "severe")


def test_elevated_river_stage_spreads_over_land_while_normal_stage_does_not():
    initial = initial_depth(2026, -0.8)
    normal, _ = step(initial, 2026, SimulationParameters(river_level_m=-0.8), steps=8)
    overflow, _ = step(initial, 2026, SimulationParameters(river_level_m=2.0), steps=8)
    land = ~channel_mask()
    assert normal[land].max() == 0
    assert overflow[land].max() > 0.3


def test_scenario_lifecycle_reset_replay_and_sqlite_restart(tmp_path):
    path = tmp_path / "scenario.sqlite3"
    store = ScenarioStore(path)
    request = ScenarioCreate(name="Test heavy rain", seed=42, preset="heavy")
    created = store.create(request, "test-create-42")
    assert store.create(request, "test-create-42").state.id == created.state.id
    scenario = created.state
    changed = store.update_parameters(scenario.id, ParameterUpdate(rainfall_mm_h=120, expected_version=scenario.state_version))
    started = store.transition(scenario.id, changed.state.state_version, "start")
    stepped = store.advance(scenario.id, AdvanceRequest(steps=3, expected_version=started.state.state_version))
    replay = store.replay(scenario.id, 2)
    assert replay.state.tick == 2
    assert replay.state.depth_m == store.replay(scenario.id, 2).state.depth_m
    assert stepped.state.tick == 3 and stepped.state.status == "running"
    assert abs(stepped.state.mass_balance.balance_error_m3) < 1e-6
    paused = store.transition(scenario.id, stepped.state.state_version, "pause")
    reset = store.reset(scenario.id, paused.state.state_version)
    assert reset.state.tick == 0 and reset.state.status == "paused"
    assert reset.state.depth_m == initial_depth(42, reset.state.parameters.river_level_m).round(4).tolist()
    reopened = ScenarioStore(path).get(scenario.id)
    assert reopened.state.state_version == reset.state.state_version
    assert reopened.events[-1].event_type == "simulation_reset"


def test_stale_version_and_illegal_transition_are_rejected(tmp_path):
    store = ScenarioStore(tmp_path / "stale.sqlite3")
    scenario = store.get(store.active_id()).state
    started = store.transition(scenario.id, scenario.state_version, "start")
    with pytest.raises(ScenarioError) as stale:
        store.transition(scenario.id, scenario.state_version, "pause")
    assert stale.value.status_code == 409
    with pytest.raises(ScenarioError) as illegal:
        store.transition(scenario.id, started.state.state_version, "resume")
    assert illegal.value.status_code == 409


def test_checkpoint_replay_keeps_parameters_for_the_selected_tick(tmp_path):
    store = ScenarioStore(tmp_path / "checkpoint.sqlite3")
    created = store.create(ScenarioCreate(name="Checkpoint", seed=42, preset="mild"), "checkpoint-create")
    running = store.transition(created.state.id, created.state.state_version, "start")
    at_twelve = store.advance(created.state.id, AdvanceRequest(steps=12, expected_version=running.state.state_version))
    changed = store.update_parameters(created.state.id, ParameterUpdate(rainfall_mm_h=180, expected_version=at_twelve.state.state_version))
    at_thirteen = store.advance(created.state.id, AdvanceRequest(steps=1, expected_version=changed.state.state_version))
    replay_twelve = store.replay(created.state.id, 12)
    replay_thirteen = store.replay(created.state.id, 13)
    assert replay_twelve.state.parameters.rainfall_mm_h == 8
    assert replay_thirteen.state.parameters.rainfall_mm_h == 180
    assert replay_thirteen.state.depth_m == at_thirteen.state.depth_m


def test_scenario_api_validates_parameters_and_supports_replay(tmp_path, monkeypatch):
    store = ScenarioStore(tmp_path / "api.sqlite3")
    monkeypatch.setattr("app.main.store", store)
    active = client.get("/api/v1/scenarios/active").json()["state"]
    invalid = client.patch(f"/api/v1/scenarios/{active['id']}/parameters", json={"rainfall_mm_h": -1, "expected_version": active["state_version"]})
    assert invalid.status_code == 422
    one_step = client.post(f"/api/v1/scenarios/{active['id']}/advance", json={"steps": 1, "single_step": True, "expected_version": active["state_version"]})
    assert one_step.status_code == 200
    assert one_step.json()["state"]["tick"] == 1
    assert client.get(f"/api/v1/scenarios/{active['id']}/replay/1").json()["state"]["depth_m"] == one_step.json()["state"]["depth_m"]
    stale = client.post(f"/api/v1/scenarios/{active['id']}/advance", json={"steps": 1, "single_step": True, "expected_version": active["state_version"]})
    assert stale.status_code == 409
    headers = {"Idempotency-Key": "scenario-create-test-001"}
    request = {"name": "Overflow test", "seed": 2026, "preset": "extreme"}
    created = client.post("/api/v1/scenarios", json=request, headers=headers)
    repeated = client.post("/api/v1/scenarios", json=request, headers=headers)
    assert created.status_code == 201
    assert repeated.json()["state"]["id"] == created.json()["state"]["id"]
    conflict = client.post("/api/v1/scenarios", json={**request, "name": "Different"}, headers=headers)
    assert conflict.status_code == 409

