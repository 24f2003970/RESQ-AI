import math
from types import SimpleNamespace
from app.city_service import generate_city
from app.rescue import build_road_graph, priorities, route, _assign
from app.rescue import PlanStore, RescuePlan
from app.scenarios import ScenarioStore
from app.schemas import ParameterUpdate, ScenarioCreate


def test_corridors_connect_at_crossings_and_bridge_is_an_edge():
    city = generate_city(2026)
    graph = build_road_graph(city)
    junction = "j:-260.000:-200.000"
    assert junction in graph
    assert graph.degree[junction] >= 3
    bridges = [(a, b, d) for a, b, d in graph.edges(data=True) if d["bridge_id"]]
    assert len(bridges) == 6
    assert all(d["length_m"] == 46 for _, _, d in bridges)
    assert nx_connected(graph)


def nx_connected(graph):
    import networkx as nx
    return nx.is_connected(graph)


def test_route_follows_graph_edges_and_boat_is_explicitly_unsupported():
    city = generate_city(2026)
    graph = build_road_graph(city)
    unit = city.rescue_units[0]
    building = city.buildings[0]
    result = route(graph, unit.position, building.position, unit.type)
    assert result["reachable"]
    assert route(graph, unit.position, building.position, unit.type)==result
    assert len(result["polyline"]) == len(result["edge_ids"]) + 1
    assert result["distance_m"] >= 0
    boat = route(graph, city.rescue_units[2].position, building.position, "boat")
    assert not boat["reachable"]
    assert "unsupported" in boat["reason"]


def test_manual_closure_removes_segment_from_accessible_route_graph():
    city = generate_city(2026)
    graph = build_road_graph(city, manual_closures=[road.id for road in city.roads])
    assert all(data["status"] == "manually_blocked" for _, _, data in graph.edges(data=True))
    assert route(graph, city.rescue_units[0].position, city.buildings[0].position, "ambulance")["reachable"] is False


def test_priority_components_respond_to_local_road_closure(tmp_path):
    state=ScenarioStore(tmp_path/"priority.sqlite3").create(ScenarioCreate(name="Priority",seed=2026,preset="heavy"),"priority-key").state
    city=generate_city(2026)
    future=SimpleNamespace(predictions=[SimpleNamespace(building_id=city.buildings[0].id,predicted_future_exposed=True,uncalibrated_model_score=.7)])
    ranked=priorities(city,state,future)
    assert ranked
    building=next(item for item in city.buildings if item.id==ranked[0]["building_id"])
    impact=next(item for item in state.impacts.buildings if item.entity_id==building.id)
    occ=min(building.occupants/100,1); depth=min(impact.max_depth_m/1.5,1)
    assert ranked[0]["priority_score"]>=100*(.25*occ+.25*bool(impact.water_reaches_building)+.15*depth)
    def road_distance(road):
        ax,ay=road.start.x_m,road.start.y_m; dx,dy=road.end.x_m-ax,road.end.y_m-ay
        t=max(0,min(1,((building.position.x_m-ax)*dx+(building.position.y_m-ay)*dy)/(dx*dx+dy*dy)))
        return math.dist((building.position.x_m,building.position.y_m),(ax+t*dx,ay+t*dy))
    road_id=min(city.roads,key=road_distance).id
    blocked=priorities(city,state,future,[road_id])
    blocked_row=next(item for item in blocked if item["building_id"]==building.id)
    assert blocked_row["priority_score"]>=ranked[0]["priority_score"]


def test_capacity_weighted_optimizer_and_nearest_baseline_are_distinct():
    units=[{"id":"near-small","capacity":1},{"id":"far-large","capacity":10}]
    destinations=[{"building_id":"zone","occupants":10,"priority_score":100}]
    routes={("near-small","zone"):{"simulated_minutes":1,"distance_m":100},("far-large","zone"):{"simulated_minutes":8,"distance_m":800}}
    assert _assign(units,destinations,routes,optimized=False)[0]["unit_id"]=="near-small"
    optimized=_assign(units,destinations,routes,optimized=True)
    assert optimized[0]["unit_id"]=="far-large"
    assert optimized[0]["occupants_targeted"]==10


def test_plan_is_persisted_and_stale_decision_is_rejected(tmp_path):
    path = tmp_path / "rescue.sqlite3"
    scenarios = ScenarioStore(path)
    state = scenarios.create(ScenarioCreate(name="Plan test", seed=2026, preset="heavy"), "rescue-test-key").state
    plans = PlanStore(path)
    plan = RescuePlan(plan_id="plan-test",scenario_id=state.id,scenario_version=state.state_version,simulation_tick=state.tick,generated_at="2026-01-01T00:00:00+00:00",priorities=[],missions=[],available_assignments=[],unreachable=[],comparison={},solver_status="optimal_exact_enumeration",objective="unit test",explanation="proposal")
    plans.save(plan)
    assert plans.get(plan.plan_id).status == "proposed"
    scenarios.update_parameters(state.id, ParameterUpdate(rainfall_mm_h=12,expected_version=state.state_version))
    import pytest
    with pytest.raises(ValueError, match="stale"):
        plans.decision(plan.plan_id,"approved",expected_version=state.state_version)
    assert plans.get(plan.plan_id).status == "superseded"


def test_plan_api_generation_closure_and_approval_controls(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as main
    import app.ml_service as ml_service
    scenario_store=ScenarioStore(tmp_path/"api.sqlite3")
    scenario=scenario_store.create(ScenarioCreate(name="API plan",seed=2026,preset="heavy"),"rescue-api-key").state
    monkeypatch.setattr(main,"store",scenario_store)
    monkeypatch.setattr(ml_service,"store",scenario_store)
    monkeypatch.setattr(main,"rescue_plans",PlanStore(scenario_store.path))
    client=TestClient(main.app)
    response=client.post(f"/api/v1/scenarios/{scenario.id}/rescue-plans")
    assert response.status_code==201
    plan=response.json()
    assert plan["status"]=="proposed"
    assert plan["solver_status"]=="optimal_exact_enumeration"
    assert len({mission["unit_id"] for mission in plan["missions"]})==len(plan["missions"])
    if plan["available_assignments"]:
        option=plan["available_assignments"][0]
        edited=client.patch(f"/api/v1/rescue-plans/{plan['plan_id']}/assignments",json={"expected_version":scenario.state_version,"assignments":[{"unit_id":option["unit_id"],"destination_id":option["destination_id"]}]})
        assert edited.status_code==200
        assert edited.json()["solver_status"]=="commander_modified"
    closed=client.post(f"/api/v1/scenarios/{scenario.id}/road-closures",json={"road_id":"road-ns-0","reason":"test"})
    assert closed.status_code==200
    assert client.get(f"/api/v1/rescue-plans/{plan['plan_id']}").json()["status"]=="superseded"
    new_plan=client.post(f"/api/v1/scenarios/{scenario.id}/rescue-plans").json()
    decision=client.post(f"/api/v1/rescue-plans/{new_plan['plan_id']}/decision",json={"action":"approved","expected_version":scenario.state_version,"reason":"reviewed"})
    assert decision.status_code==200
    assert decision.json()["status"]=="approved"
