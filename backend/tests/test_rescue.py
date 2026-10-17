import math
import time
from types import SimpleNamespace
from app.city_service import generate_city
from app.rescue import build_road_graph, priorities, route, _assign, generate_plan
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


def test_all_corridors_closed_never_produces_ground_assignments(tmp_path):
    city=generate_city(2026)
    state=ScenarioStore(tmp_path/"all-roads-closed.sqlite3").create(
        ScenarioCreate(name="All roads closed",seed=2026,preset="heavy"),"all-roads-closed-key").state
    predictions=SimpleNamespace(predictions=[])
    closed=[road.id for road in city.roads]
    graph=build_road_graph(city,state,closed)
    plan=generate_plan(city,state,predictions,closed)
    assert route(graph,city.rescue_units[0].position,city.buildings[0].position,"ambulance")["reachable"] is False
    assert plan.missions==[]
    assert plan.available_assignments==[]
    assert all("traversable road corridor" in item["reason"] for item in plan.unreachable)


def test_two_access_spurs_cannot_bypass_a_closed_isolated_intersection():
    city=generate_city(2026)
    open_graph=build_road_graph(city)
    isolated=next(node for node in open_graph.nodes if open_graph.degree[node]>0)
    incident_roads={data["road_id"] for _,_,data in open_graph.edges(isolated,data=True)}
    graph=build_road_graph(city,manual_closures=incident_roads)
    x,y=graph.nodes[isolated]["xy"]
    position={"x_m":x,"y_m":y,"elevation_m":0.0}
    result=route(graph,position,position,"ambulance")
    assert result["reachable"] is False
    assert "access spurs alone" in result["reason"] or "traversable road corridor" in result["reason"]


def test_co_located_endpoints_on_a_permitted_intersection_are_explicitly_allowed():
    city=generate_city(2026)
    graph=build_road_graph(city)
    node=next(node for node in graph.nodes if graph.degree[node]>0)
    x,y=graph.nodes[node]["xy"]
    position={"x_m":x,"y_m":y,"elevation_m":graph.nodes[node]["elevation_m"]}
    result=route(graph,position,position,"ambulance")
    assert result["reachable"] is True
    assert result["accessibility"]=="co_located_on_open_road_network"
    assert result["road_ids"]==[] and result["distance_m"]==0


def test_open_detour_and_building_access_spur_survive_a_single_road_closure():
    city=generate_city(2026)
    baseline_graph=build_road_graph(city)
    found=None
    for unit in city.rescue_units:
        if unit.type=="boat":continue
        for building in city.buildings:
            baseline=route(baseline_graph,unit.position,building.position,unit.type)
            if not baseline["reachable"] or not baseline["road_ids"]:continue
            for road_id in baseline["road_ids"]:
                changed=route(build_road_graph(city,manual_closures=[road_id]),unit.position,building.position,unit.type)
                if changed["reachable"] and road_id not in changed["road_ids"]:
                    found=(unit,building,road_id,changed)
                    break
            if found:break
        if found:break
    assert found is not None,"the synthetic grid should have a genuine alternate corridor"
    unit,building,closed_road,detour=found
    assert closed_road not in detour["road_ids"]
    assert detour["road_ids"]
    assert "access:unit" in detour["edge_ids"] and "access:building" in detour["edge_ids"]
    graph=build_road_graph(city,manual_closures=[closed_road])
    by_edge={data["edge_id"]:data for _,_,data in graph.edges(data=True)}
    for edge_id in detour["edge_ids"]:
        if edge_id.startswith("access:"):continue
        assert edge_id in by_edge
        assert by_edge[edge_id]["status"] not in ("closed","flooded","manually_blocked")
        assert by_edge[edge_id]["road_id"]!=closed_road


def test_shared_router_enforces_unit_depth_limits_and_connected_edge_references():
    import networkx as nx
    graph=nx.Graph()
    graph.add_node("a",xy=(0.0,0.0),elevation_m=0.0,kind="intersection")
    graph.add_node("b",xy=(100.0,0.0),elevation_m=0.0,kind="intersection")
    graph.add_edge("a","b",edge_id="road-test:segment:0-1",road_id="road-test",bridge_id=None,
        length_m=100.0,xy=[(0.0,0.0),(100.0,0.0)],status="open",depth_m=.16,speed_kmh=30.0)
    start={"x_m":0.0,"y_m":0.0,"elevation_m":0.0};end={"x_m":100.0,"y_m":0.0,"elevation_m":0.0}
    ambulance=route(graph,start,end,"ambulance")
    rescue_team=route(graph,start,end,"rescue_team")
    assert ambulance["reachable"] is False
    assert rescue_team["reachable"] is True
    assert rescue_team["edge_ids"].count("road-test:segment:0-1")==1
    graph.edges["a","b"]["depth_m"]=.31
    assert route(graph,start,end,"rescue_team")["reachable"] is False


def test_bridge_closure_removes_the_span_from_every_returned_route(tmp_path):
    from app.robustness import Counterfactual, RobustnessRunner
    city=generate_city(2026)
    bridge=city.bridges[0]
    base=build_road_graph(city)
    crossing=None
    for unit in city.rescue_units:
        if unit.type=="boat":continue
        for building in city.buildings:
            candidate=route(base,unit.position,building.position,unit.type)
            if not candidate["reachable"]:continue
            if any(edge_id in {data["edge_id"] for _,_,data in base.edges(data=True) if data.get("bridge_id")==bridge.id}
                   for edge_id in candidate["edge_ids"]):
                crossing=(unit,building)
                break
        if crossing:break
    if crossing is None:
        pytest.skip("the deterministic city has no assigned test pair crossing the selected bridge")
    unit,building=crossing
    condition=Counterfactual(condition_id="closed-bridge",label="Bridge closed",category="bridge_closure",closed_asset_ids=[bridge.id])
    state=ScenarioStore(tmp_path/"bridge-route.sqlite3").create(ScenarioCreate(name="Bridge",seed=2026),"bridge-state").state
    altered=RobustnessRunner._apply_bridge_closures(state,city,condition)
    closed_graph=build_road_graph(city,altered,[])
    result=route(closed_graph,unit.position,building.position,unit.type)
    closed_span_ids={data["edge_id"] for _,_,data in closed_graph.edges(data=True) if data.get("bridge_id")==bridge.id}
    if result["reachable"]:
        assert not closed_span_ids.intersection(result["edge_ids"])


def test_priority_components_respond_to_local_road_closure(tmp_path):
    state=ScenarioStore(tmp_path/"priority.sqlite3").create(ScenarioCreate(name="Priority",seed=2026,preset="heavy"),"priority-key").state
    city=generate_city(2026)
    future=SimpleNamespace(predictions=[SimpleNamespace(building_id=city.buildings[0].id,predicted_future_exposed=True,uncalibrated_model_score=.7,distribution_support_status="within_observed_support")])
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


def test_out_of_support_future_label_does_not_create_a_forecast_destination(tmp_path):
    state=ScenarioStore(tmp_path/"priority-support.sqlite3").create(ScenarioCreate(name="Support",seed=12,preset="mild"),"priority-support-key").state
    city=generate_city(12)
    physical={item.entity_id:item.water_reaches_building for item in state.impacts.buildings}
    dry=next(building for building in city.buildings if not physical[building.id])
    future=SimpleNamespace(predictions=[SimpleNamespace(building_id=dry.id,predicted_future_exposed=True,
        uncalibrated_model_score=.99,distribution_support_status="outside_observed_support")])
    ranked=priorities(city,state,future)
    assert dry.id not in {item["building_id"] for item in ranked}


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
    plans.infrastructure(state.id,state.epoch)
    plan = RescuePlan(plan_id="plan-test",scenario_id=state.id,scenario_version=state.state_version,scenario_epoch=state.epoch,infrastructure_revision=0,simulation_tick=state.tick,generated_at="2026-01-01T00:00:00+00:00",priorities=[],missions=[],available_assignments=[],unreachable=[],comparison={},solver_status="optimal_linear_sum_assignment",objective="unit test",explanation="proposal")
    plans.save(plan)
    assert plans.get(plan.plan_id).status == "proposed"
    scenarios.update_parameters(state.id, ParameterUpdate(rainfall_mm_h=12,expected_version=state.state_version))
    import pytest
    with pytest.raises(ValueError, match="stale"):
        plans.decision(plan.plan_id,"approved",expected_version=state.state_version)
    assert plans.get(plan.plan_id).status == "superseded"


def test_already_reserved_unit_is_rejected_when_saving_a_second_proposal(tmp_path):
    import pytest
    path=tmp_path/"conflict.sqlite3"
    scenarios=ScenarioStore(path)
    state=scenarios.create(ScenarioCreate(name="Conflict",seed=2026,preset="heavy"),"conflict-test-key").state
    plans=PlanStore(path);plans.infrastructure(state.id,state.epoch)
    mission={"unit_id":"unit-ground-0","destination_id":"zone-a"}
    def make(plan_id):
        return RescuePlan(plan_id=plan_id,scenario_id=state.id,scenario_version=state.state_version,scenario_epoch=state.epoch,infrastructure_revision=0,simulation_tick=state.tick,generated_at="2026-01-01T00:00:00+00:00",priorities=[],missions=[mission],available_assignments=[],unreachable=[],comparison={},solver_status="optimal_linear_sum_assignment",objective="unit test",explanation="proposal")
    first,second=make("approved-plan"),make("conflicting-plan")
    plans.save(first)
    plans.decision(first.plan_id,"approved",expected_version=state.state_version)
    with pytest.raises(ValueError,match="Resources became unavailable"):
        plans.save(second)


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
    assert plan["solver_status"]=="optimal_linear_sum_assignment"
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
    reserved={m["unit_id"] for m in decision.json()["missions"]}
    another=client.post(f"/api/v1/scenarios/{scenario.id}/rescue-plans")
    assert another.status_code==201
    assert not reserved & {m["unit_id"] for m in another.json()["missions"]}


def test_linear_assignment_scales_to_72_destinations():
    units=[unit.model_dump() for unit in generate_city(2026).rescue_units if unit.status=="standby" and unit.type!="boat"]
    destinations=[{"building_id":f"zone-{i:02}","occupants":30+i,"priority_score":90-i/4} for i in range(72)]
    routes={(u["id"],d["building_id"]):{"simulated_minutes":float((i+j)%20+1),"distance_m":100.0}
            for i,u in enumerate(units) for j,d in enumerate(destinations)}
    start=time.perf_counter()
    result=_assign(units,destinations,routes)
    elapsed=time.perf_counter()-start
    print(f"72 destinations / 4 ground units optimizer: {elapsed:.6f}s")
    assert len(result)==4
    assert elapsed<2


def test_road_closure_during_generation_rejects_snapshot(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as main
    import app.ml_service as ml_service
    scenarios=ScenarioStore(tmp_path/"race.sqlite3")
    state=scenarios.create(ScenarioCreate(name="Race",seed=2026,preset="heavy"),"closure-race-key").state
    plans=PlanStore(scenarios.path)
    monkeypatch.setattr(main,"store",scenarios);monkeypatch.setattr(ml_service,"store",scenarios);monkeypatch.setattr(main,"rescue_plans",plans)
    client=TestClient(main.app)
    original=main.generate_plan
    def close_mid_generation(*args,**kwargs):
        plan=original(*args,**kwargs)
        closure=client.post(f"/api/v1/scenarios/{state.id}/road-closures",json={"road_id":"road-ns-0","reason":"closed during planning"})
        assert closure.status_code==200
        return plan
    monkeypatch.setattr(main,"generate_plan",close_mid_generation)
    response=client.post(f"/api/v1/scenarios/{state.id}/rescue-plans")
    assert response.status_code==409


def test_closure_invalidates_proposal_and_reset_starts_clean_epoch(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as main
    import app.ml_service as ml_service
    scenarios=ScenarioStore(tmp_path/"epochs.sqlite3")
    state=scenarios.create(ScenarioCreate(name="Epoch",seed=2026,preset="heavy"),"epoch-test-key").state
    plans=PlanStore(scenarios.path)
    monkeypatch.setattr(main,"store",scenarios);monkeypatch.setattr(ml_service,"store",scenarios);monkeypatch.setattr(main,"rescue_plans",plans)
    client=TestClient(main.app)
    plan=client.post(f"/api/v1/scenarios/{state.id}/rescue-plans").json()
    assert plan["infrastructure_revision"]==0 and plan["scenario_epoch"]==0
    closed=client.post(f"/api/v1/scenarios/{state.id}/road-closures",json={"road_id":"road-ns-0","reason":"blocked"})
    assert closed.status_code==200 and closed.json()["infrastructure_revision"]==1
    assert client.patch(f"/api/v1/rescue-plans/{plan['plan_id']}/assignments",json={"expected_version":state.state_version,"assignments":[]}).status_code==409
    assert client.post(f"/api/v1/rescue-plans/{plan['plan_id']}/decision",json={"action":"approved","expected_version":state.state_version}).status_code==409
    assert client.get(f"/api/v1/rescue-plans/{plan['plan_id']}").json()["status"]=="superseded"
    reset=scenarios.reset(state.id,state.state_version).state
    assert reset.epoch==1
    revision,closures=plans.infrastructure(state.id,reset.epoch)
    assert revision==0 and closures==[]
    client.post(f"/api/v1/scenarios/{state.id}/road-closures",json={"road_id":"road-ns-0","reason":"epoch closure"})
    replay=scenarios.replay(state.id,0).state
    assert replay.epoch==reset.epoch
    assert plans.infrastructure(state.id,replay.epoch)[1]==["road-ns-0"]
