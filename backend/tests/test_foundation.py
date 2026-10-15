import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.city_service import generate_city
from app.main import app
from app.schemas import CityState

client = TestClient(app)


def test_seed_is_repeatable_and_variants_differ():
    a = generate_city(2026).model_dump()
    generate_city.cache_clear()
    assert a == generate_city(2026).model_dump()
    assert a["buildings"] != generate_city(2027).model_dump()["buildings"]


def test_relationships_bounds_and_inventory():
    state = generate_city()
    assert len(state.buildings) == 72
    assert len(state.rescue_units) == 5
    for building in state.buildings:
        assert abs(building.position.x_m) + building.width_m / 2 < state.city.width_m / 2
        assert abs(building.position.y_m) + building.depth_m / 2 < state.city.depth_m / 2
    assert all(bridge.road_id in {r.id for r in state.roads} for bridge in state.bridges)


def test_schema_rejects_invalid_relationship_and_negative_dimension():
    payload = generate_city().model_dump()
    payload["buildings"][0]["district_id"] = "missing"
    with pytest.raises(ValidationError):
        CityState.model_validate(payload)
    payload = generate_city().model_dump()
    payload["buildings"][0]["width_m"] = -1
    with pytest.raises(ValidationError):
        CityState.model_validate(payload)


def test_health_state_and_details_match():
    health = client.get("/api/v1/health")
    assert health.status_code == 200 and health.json()["mode"] == "local"
    response = client.get("/api/v1/city/state")
    assert response.status_code == 200
    state = CityState.model_validate(response.json())
    building = state.buildings[0]
    assert client.get(f"/api/v1/city/buildings/{building.id}").json() == building.model_dump()
    assert client.get("/api/v1/scenarios/default").json()["city_id"] == state.city.id
    assert response.headers["X-Request-ID"]


def test_missing_building_is_useful_error():
    response = client.get("/api/v1/city/buildings/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_local_cors_and_no_wildcard_access():
    allowed = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    denied = client.get("/api/v1/health", headers={"Origin": "https://untrusted.example"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in denied.headers


@pytest.mark.parametrize("mutation", ["duplicate_id", "missing_node", "unknown_field", "nonfinite"])
def test_contract_rejects_corrupt_state(mutation):
    payload = generate_city().model_dump()
    if mutation == "duplicate_id":
        payload["buildings"][1]["id"] = payload["buildings"][0]["id"]
    elif mutation == "missing_node":
        payload["roads"][0]["from_node"] = "missing"
    elif mutation == "unknown_field":
        payload["buildings"][0]["predicted_risk"] = "invented"
    else:
        payload["buildings"][0]["position"]["x_m"] = float("inf")
    with pytest.raises(ValidationError):
        CityState.model_validate(payload)
