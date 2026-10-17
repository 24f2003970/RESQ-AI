import sqlite3
import threading
import math

import pytest

from app.city_service import generate_city
from app.missions import MissionClockAdvance, MissionStore
from app.rescue import PlanStore, RescuePlan, build_road_graph, route, route_from_mission_segment
from app.scenarios import ScenarioStore
from app.schemas import ScenarioCreate, VersionRequest


def fixture(tmp_path, use_real_route=False):
    path=tmp_path/"missions.sqlite3"
    scenarios=ScenarioStore(path)
    state=scenarios.create(ScenarioCreate(name="Mission lifecycle",seed=2026,preset="mild"),"mission-scenario-key").state
    plans=PlanStore(path)
    revision,closures=plans.infrastructure(state.id,state.epoch)
    city=generate_city(state.seed)
    if use_real_route:
        unit=next(unit for unit in city.rescue_units if unit.id=="unit-1")
        destination=next(building for building in city.buildings if building.id=="building-0-0-0")
        route_result=route(build_road_graph(city,state,closures),unit.position,destination.position,unit.type)
        assert route_result["reachable"]
        unit_id,unit_type,capacity=unit.id,unit.type,unit.capacity
        destination_id=destination.id
    else:
        route_result={"reachable":True,"distance_m":200,"simulated_minutes":0.3,
          "polyline":[[0,0],[100,0],[100,100]],"polyline_xyz":[[0,0,0],[100,0,0],[100,100,0]],
          "segment_lengths_m":[100,100],"segment_speeds_mps":[10,10],
          "edge_ids":["road-a:segment:0-1","road-b:segment:0-1"],"road_ids":["road-a","road-b"]}
        unit_id,unit_type,capacity="unit-test","rescue_team",4
        destination_id="building-hospital"
    plan=RescuePlan(plan_id="plan-test",scenario_id=state.id,scenario_version=state.state_version,
      scenario_epoch=state.epoch,infrastructure_revision=revision,simulation_tick=state.tick,
      generated_at="2026-10-01T00:00:00+00:00",priorities=[],
      missions=[{"unit_id":unit_id,"unit_type":unit_type,"destination_id":destination_id,
        "unit_capacity":capacity,"occupants_targeted":2,"route":route_result}],
      available_assignments=[],unreachable=[],comparison={},solver_status="test",objective="test",explanation="test")
    plans.save(plan)
    approved=plans.decision(plan.plan_id,"approved",expected_version=state.state_version)
    mission_store=MissionStore(str(path))
    mission=mission_store.list(state.id,state.epoch)[0]
    return path,scenarios,plans,mission_store,city,state,approved,mission


def test_approval_creates_one_ready_mission_and_reservation_idempotently(tmp_path):
    path,scenarios,plans,store,city,state,approved,mission=fixture(tmp_path)
    assert mission.status=="ready"
    assert mission.plan_id==approved.plan_id
    assert mission.simulation_version==state.state_version
    assert mission.route["edge_ids"]==["road-a:segment:0-1","road-b:segment:0-1"]
    assert mission.estimated_remaining_seconds==20
    assert plans.reserved_units(state.id,state.epoch)=={"unit-test"}
    with pytest.raises(ValueError): plans.decision(approved.plan_id,"approved",expected_version=state.state_version)
    assert len(store.list(state.id,state.epoch))==1
    reopened=MissionStore(str(path))
    assert reopened.get(mission.mission_id).mission_version==1


def test_no_movement_before_dispatch_and_deterministic_segment_progress(tmp_path):
    path,scenarios,plans,store,city,state,approved,mission=fixture(tmp_path)
    clock=store.clock(state.id,state.epoch)
    clock,unchanged=store.advance(state.id,state.epoch,clock.version,state.state_version,5,idempotency_key="clock-before-dispatch")
    assert unchanged==[]
    dispatched=store.command(mission.mission_id,"dispatch",mission.mission_version,idempotency_key="dispatch-once")
    assert dispatched.status=="en_route" and dispatched.traversed_distance_m==0
    clock,updated=store.advance(state.id,state.epoch,clock.version,state.state_version,5,idempotency_key="clock-progress-1")
    assert updated[0].traversed_distance_m==50
    assert updated[0].position=={"x_m":50.0,"y_m":0.0,"elevation_m":0.0}
    # Retrying the same idempotency key returns the same authoritative snapshot.
    same_clock,same=store.advance(state.id,state.epoch,clock.version-1,state.state_version,5,idempotency_key="clock-progress-1")
    assert same_clock.seconds==clock.seconds and same[0].traversed_distance_m==50


def test_dispatch_rejects_missing_authoritative_unit_reservation(tmp_path):
    path,scenarios,plans,store,city,state,approved,mission=fixture(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM unit_resources WHERE mission_id=?",(mission.mission_id,))
    with pytest.raises(ValueError,match="no longer owns a reserved unit"):
        store.command(mission.mission_id,"dispatch",mission.mission_version)
    assert store.get(mission.mission_id).status=="ready"


def test_clock_pause_stops_motion_and_arrival_is_not_completion(tmp_path):
    path,scenarios,plans,store,city,state,approved,mission=fixture(tmp_path)
    mission=store.command(mission.mission_id,"dispatch",mission.mission_version,idempotency_key="dispatch-pause-test")
    clock=store.clock(state.id,state.epoch)
    clock=store.set_paused(state.id,state.epoch,clock.version,True,"pause-clock-key")
    assert store.set_paused(state.id,state.epoch,clock.version-1,True,"pause-clock-key").version==clock.version
    with pytest.raises(ValueError,match="paused"):
        store.advance(state.id,state.epoch,clock.version,state.state_version,10)
    clock=store.set_paused(state.id,state.epoch,clock.version,False)
    clock,updated=store.advance(state.id,state.epoch,clock.version,state.state_version,30)
    assert updated[0].status=="arrived"
    assert updated[0].arrival_clock_seconds is not None
    with pytest.raises(ValueError,match="ready"):
        store.command(mission.mission_id,"dispatch",updated[0].mission_version,idempotency_key="duplicate-dispatch")
    completed=store.command(mission.mission_id,"complete",updated[0].mission_version,idempotency_key="complete-once")
    assert completed.status=="completed"
    assert store.units(state.id,state.epoch)[0]["status"]=="unavailable"
    restored=store.command(mission.mission_id,"restore",completed.mission_version,idempotency_key="restore-once")
    assert restored.status=="completed"
    resource=store.units(state.id,state.epoch)[0]
    assert resource["status"]=="available"
    assert resource["position"]==restored.position
    assert plans.reserved_units(state.id,state.epoch)==set()
    # Approved-plan migration runs at application startup; it must not
    # resurrect the old reservation after an explicit return-to-service.
    PlanStore(str(path))
    restarted=MissionStore(str(path))
    assert restarted.units(state.id,state.epoch)[0]["status"]=="available"
    assert plans.reserved_units(state.id,state.epoch)==set()


def test_closure_only_blocks_a_remaining_route_edge(tmp_path):
    path,scenarios,plans,store,city,state,approved,mission=fixture(tmp_path)
    mission=store.command(mission.mission_id,"dispatch",mission.mission_version,idempotency_key="dispatch-closure")
    clock=store.clock(state.id,state.epoch)
    clock,updated=store.advance(state.id,state.epoch,clock.version,state.state_version,11)
    mission=updated[0]
    assert mission.traversed_distance_m==110
    assert store.infrastructure_changed(state.id,state.epoch,1,{"road-a"})==[]
    assert store.get(mission.mission_id).status=="en_route"
    blocked=store.infrastructure_changed(state.id,state.epoch,2,{"road-b"})
    assert blocked==[mission.mission_id]
    assert store.get(mission.mission_id).status=="blocked"
    assert plans.reserved_units(state.id,state.epoch)=={"unit-test"}


def test_route_revision_requires_explicit_approval_and_records_new_version(tmp_path):
    path,scenarios,plans,store,city,state,approved,mission=fixture(tmp_path,use_real_route=True)
    mission=store.command(mission.mission_id,"dispatch",mission.mission_version,idempotency_key="dispatch-route-revision")
    road=mission.route["road_ids"][0]
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO road_closures(scenario_id,epoch,road_id,reason,active) VALUES(?,?,?,?,1)",(state.id,state.epoch,road,"test closure"))
        db.execute("UPDATE scenario_infrastructure SET revision=revision+1 WHERE scenario_id=? AND epoch=?",(state.id,state.epoch))
    rev,closures=plans.infrastructure(state.id,state.epoch)
    assert store.infrastructure_changed(state.id,state.epoch,rev,set(closures))==[mission.mission_id]
    blocked=store.get(mission.mission_id)
    recommendation=store.propose_route(blocked.mission_id,blocked.mission_version,city,state,closures,rev,"route-proposal-once")
    assert store.propose_route(blocked.mission_id,blocked.mission_version,city,state,closures,rev,"route-proposal-once").route_proposal==recommendation.route_proposal
    assert recommendation.status=="blocked"
    assert recommendation.route_proposal is not None
    with pytest.raises(ValueError,match="stale"):
        store.approve_route(blocked.mission_id,blocked.mission_version,recommendation.route_proposal["route_revision_id"],state,rev+1)
    route_id=recommendation.route_proposal["route_revision_id"]
    resumed=store.approve_route(blocked.mission_id,recommendation.mission_version,route_id,state,rev,"approve-route-once")
    assert store.approve_route(blocked.mission_id,recommendation.mission_version,route_id,state,rev,"approve-route-once").mission_version==resumed.mission_version
    assert resumed.status=="en_route" and resumed.route_revision==2
    assert resumed.position==blocked.position


def test_midroute_reroute_uses_open_geometry_and_rejects_closed_current_segment(tmp_path):
    path,scenarios,plans,store,city,state,approved,mission=fixture(tmp_path,use_real_route=True)
    mission=store.command(mission.mission_id,"dispatch",mission.mission_version,idempotency_key="dispatch-midroute")
    clock=store.clock(state.id,state.epoch)
    clock,updated=store.advance(state.id,state.epoch,clock.version,state.state_version,20)
    mission=updated[0]
    assert mission.traversed_distance_m>18
    assert mission.route_segment_index==1
    assert mission.position["x_m"] < -156 and mission.position["y_m"]==-100

    # Close the downstream north-south road while the unit is on the open east-west segment.
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO road_closures(scenario_id,epoch,road_id,reason,active) VALUES(?,?,?,?,1)",
                   (state.id,state.epoch,"road-ns-0","closure ahead"))
        db.execute("UPDATE scenario_infrastructure SET revision=revision+1 WHERE scenario_id=? AND epoch=?",
                   (state.id,state.epoch))
    rev,closures=plans.infrastructure(state.id,state.epoch)
    assert store.infrastructure_changed(state.id,state.epoch,rev,set(closures))==[mission.mission_id]
    blocked=store.get(mission.mission_id)
    proposal=store.propose_route(blocked.mission_id,blocked.mission_version,city,state,closures,rev)
    replacement=proposal.route_proposal["route"]
    assert replacement["reachable"]
    assert replacement["polyline"][0]==[blocked.position["x_m"],blocked.position["y_m"]]
    assert "road-ns-0" not in replacement["road_ids"]

    # Every graph-road segment is backed by an open source edge, and each pair
    # of consecutive route points is the corresponding physical edge geometry.
    graph=build_road_graph(city,state,closures)
    source_edges={data["edge_id"]: (graph.nodes[a]["xy"],graph.nodes[b]["xy"],data)
                  for a,b,data in graph.edges(data=True)}
    points=replacement["polyline"]
    for index,edge_id in enumerate(replacement["edge_ids"]):
        start,end=points[index],points[index+1]
        if edge_id=="access:building":
            assert math.dist(start,end)<=90
            continue
        assert edge_id in source_edges
        edge_a,edge_b,data=source_edges[edge_id]
        assert data["status"] not in {"closed","flooded","manually_blocked"}
        assert math.dist(start,end)<=data["length_m"]+1e-5
        assert (math.dist(start,edge_a)+math.dist(end,edge_b)<=data["length_m"]+1e-4
                or math.dist(start,edge_b)+math.dist(end,edge_a)<=data["length_m"]+1e-4)

    resumed=store.approve_route(blocked.mission_id,proposal.mission_version,
        proposal.route_proposal["route_revision_id"],state,rev,"approve-midroute-reroute")
    clock_after_revision=store.clock(state.id,state.epoch)
    _,progress_after_revision=store.advance(state.id,state.epoch,clock_after_revision.version,state.state_version,1)
    progress_after_revision=next(item for item in progress_after_revision if item.mission_id==mission.mission_id)
    current_road=next((edge.split(":",1)[0] for edge in progress_after_revision.route["edge_ids"][progress_after_revision.route_segment_index:]
                       if not edge.startswith("access:")),None)
    future_road=next((edge.split(":",1)[0] for edge in progress_after_revision.route["edge_ids"][progress_after_revision.route_segment_index+1:]
                      if not edge.startswith("access:") and edge.split(":",1)[0]!=current_road),None)
    assert future_road is not None
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO road_closures(scenario_id,epoch,road_id,reason,active) VALUES(?,?,?,?,1)",
                   (state.id,state.epoch,future_road,"second downstream closure"))
        db.execute("UPDATE scenario_infrastructure SET revision=revision+1 WHERE scenario_id=? AND epoch=?",
                   (state.id,state.epoch))
    next_revision,next_closures=plans.infrastructure(state.id,state.epoch)
    assert store.infrastructure_changed(state.id,state.epoch,next_revision,set(next_closures))==[mission.mission_id]
    blocked_again=store.get(mission.mission_id)
    second_proposal=store.propose_route(blocked_again.mission_id,blocked_again.mission_version,
        city,state,next_closures,next_revision)
    assert second_proposal.route_proposal["route"]["reachable"]
    assert future_road not in second_proposal.route_proposal["route"].get("road_ids",[])

    # A separate scenario closes the road segment underneath a stopped unit;
    # no synthetic free spur may make that impassable edge traversable.
    second_dir=tmp_path/"closed-current"
    second_dir.mkdir()
    path2,scenarios2,plans2,store2,city2,state2,approved2,mission2=fixture(second_dir,use_real_route=True)
    mission2=store2.command(mission2.mission_id,"dispatch",mission2.mission_version,idempotency_key="dispatch-on-closed")
    clock2=store2.clock(state2.id,state2.epoch)
    clock2,updated2=store2.advance(state2.id,state2.epoch,clock2.version,state2.state_version,20)
    mission2=updated2[0]
    with sqlite3.connect(path2) as db:
        db.execute("INSERT INTO road_closures(scenario_id,epoch,road_id,reason,active) VALUES(?,?,?,?,1)",
                   (state2.id,state2.epoch,"road-ew-1","current segment closed"))
        db.execute("UPDATE scenario_infrastructure SET revision=revision+1 WHERE scenario_id=? AND epoch=?",
                   (state2.id,state2.epoch))
    rev2,closures2=plans2.infrastructure(state2.id,state2.epoch)
    store2.infrastructure_changed(state2.id,state2.epoch,rev2,set(closures2))
    blocked2=store2.get(mission2.mission_id)
    with pytest.raises(ValueError,match="No safe replacement route"):
        store2.propose_route(blocked2.mission_id,blocked2.mission_version,city2,state2,closures2,rev2)


def test_cancel_and_epoch_reset_preserve_history_and_resource_safety(tmp_path):
    path,scenarios,plans,store,city,state,approved,mission=fixture(tmp_path)
    dispatched=store.command(mission.mission_id,"dispatch",mission.mission_version,idempotency_key="dispatch-cancel")
    cancelled=store.command(mission.mission_id,"cancel",dispatched.mission_version,idempotency_key="cancel-dispatched",reason="simulation operator stopped test")
    assert cancelled.status=="cancelled"
    assert store.units(state.id,state.epoch)[0]["status"]=="unavailable"
    restored=store.command(cancelled.mission_id,"restore",cancelled.mission_version,idempotency_key="restore-cancelled")
    assert restored.position==cancelled.position
    assert store.units(state.id,state.epoch)[0]["status"]=="available"
    reset=scenarios.reset(state.id,state.state_version)
    assert reset.state.epoch==state.epoch+1
    with pytest.raises(ValueError,match="historical"):
        store.command(mission.mission_id,"dispatch",mission.mission_version,idempotency_key="dispatch-old-epoch")
    before=store.units(state.id,state.epoch+1)
    assert before==[]
    assert [event.event_type for event in store.replay(mission.mission_id)][0]=="mission_created"


def test_concurrent_dispatch_has_a_single_winner(tmp_path):
    path,scenarios,plans,store,city,state,approved,mission=fixture(tmp_path)
    results=[]
    def dispatch(key):
        try: results.append(store.command(mission.mission_id,"dispatch",mission.mission_version,idempotency_key=key).status)
        except ValueError as exc: results.append(str(exc))
    threads=[threading.Thread(target=dispatch,args=(f"dispatch-race-{i}",)) for i in range(2)]
    [thread.start() for thread in threads];[thread.join() for thread in threads]
    assert results.count("en_route")==1
    assert sum(result!="en_route" for result in results)==1


def test_typed_mission_api_persists_dispatch_and_clock_progress(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from app.agents import AgentOrchestrator
    path,scenarios,plans,store,city,state,approved,mission=fixture(tmp_path)
    class NoopAgents:
        @staticmethod
        def recover(): pass
        @staticmethod
        def schedule_pending(*_args,**_kwargs): pass
    monkeypatch.setattr(main,"store",scenarios)
    monkeypatch.setattr(main,"rescue_plans",plans)
    monkeypatch.setattr(main,"missions",store)
    monkeypatch.setattr(main,"agent_orchestrator",NoopAgents())
    with TestClient(main.app) as client:
        listed=client.get(f"/api/v1/scenarios/{state.id}/missions")
        assert listed.status_code==200 and listed.json()[0]["status"]=="ready"
        dispatched=client.post(f"/api/v1/missions/{mission.mission_id}/dispatch",headers={"Idempotency-Key":"api-dispatch-001"},json={"expected_version":mission.mission_version})
        assert dispatched.status_code==200 and dispatched.json()["status"]=="en_route"
        with sqlite3.connect(path) as db:
            queued=[(__import__("json").loads(row[0])["event_id"],__import__("json").loads(row[0])["event_type"]) for row in db.execute("SELECT envelope_json FROM agent_event_outbox")]
        dispatch_event=next(event_id for event_id,event_type in queued if event_type=="mission_dispatched")
        from types import SimpleNamespace
        monkeypatch.setattr("app.agents.predictions",lambda _scenario_id:SimpleNamespace(model_version="mission-test",reliability_status="available",calibration_status="adopted",reliability_warnings=[],predictions=[]))
        orchestrator=AgentOrchestrator(scenarios,plans)
        orchestrator.process_event(dispatch_event)
        trace=orchestrator.get_trace(dispatch_event)
        assert trace is not None and trace.event_status=="completed"
        assert len(trace.agents)==6
        clock=client.get(f"/api/v1/scenarios/{state.id}/missions/clock").json()
        moved=client.post(f"/api/v1/scenarios/{state.id}/missions/clock/advance",headers={"Idempotency-Key":"api-clock-advance-001"},json={
            "expected_version":clock["version"],"expected_state_version":state.state_version,"seconds":5})
        assert moved.status_code==200
        assert moved.json()["missions"][0]["traversed_distance_m"]==50
        resources=client.get(f"/api/v1/scenarios/{state.id}/missions/units")
        assert resources.status_code==200 and resources.json()[0]["status"]=="en_route"
