from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import sqlite3
import time

from app.agents import AGENT_NAMES, AgentOrchestrator
from app.city_service import generate_city
from app.ml_service import ModelUnavailable
from app.rescue import PlanStore
from app.scenarios import ScenarioStore
from app.schemas import AdvanceRequest, ParameterUpdate, ScenarioCreate


def _system(tmp_path, monkeypatch, *, model=True, preset="extreme"):
    path=tmp_path/"agents.sqlite3"
    scenarios=ScenarioStore(path)
    state=scenarios.create(ScenarioCreate(name="Agent test",seed=2026,preset=preset),"agent-create-key").state
    plans=PlanStore(path)
    city=generate_city(state.seed)
    if model:
        pred=SimpleNamespace(model_version="test-local",reliability_status="available",calibration_status="adopted",reliability_warnings=[],predictions=[SimpleNamespace(building_id=b.id,predicted_future_exposed=True,uncalibrated_model_score=.8,distribution_support_status="within_observed_support") for b in city.buildings[:8]])
        monkeypatch.setattr("app.agents.predictions",lambda _scenario_id:pred)
    else:
        def unavailable(_scenario_id):raise ModelUnavailable("test model unavailable")
        monkeypatch.setattr("app.agents.predictions",unavailable)
    return path,scenarios,plans,state,AgentOrchestrator(scenarios,plans)


def _event(orchestrator,state,plans,event_type="manual_assessment"):
    revision,closures=plans.infrastructure(state.id,state.epoch)
    return orchestrator.enqueue(event_type=event_type,scenario_id=state.id,state=state,
        infrastructure_revision=revision,source_module="test",payload={"active_manual_closures":closures})


def test_ordered_pipeline_persists_explainable_human_review_proposal_and_is_idempotent(tmp_path,monkeypatch):
    path,scenarios,plans,state,orchestrator=_system(tmp_path,monkeypatch)
    event=_event(orchestrator,state,plans)
    started=time.perf_counter();orchestrator.process_event(event.event_id);elapsed_ms=(time.perf_counter()-started)*1000
    detail=orchestrator.get_trace(event.event_id)
    assert detail.event_status=="completed"
    assert [run.agent_name for run in detail.agents]==AGENT_NAMES
    assert all(run.status in ("completed","degraded") for run in detail.agents)
    assert detail.trace.evidence["pipeline_duration_ms"]>0
    assert detail.trace.evidence["event_ingestion_ms"] is not None
    assert detail.trace.evidence["ml_inference_ms"] is not None
    assert detail.trace.evidence["routing_duration_ms"] is not None
    assert detail.trace.evidence["resource_allocation_duration_ms"] is not None
    assert detail.trace.evidence["model_reliability_status"]=="available"
    assert detail.trace.evidence["model_calibration_status"]=="adopted"
    assert elapsed_ms < 5000
    if detail.related_plan:
        assert detail.related_plan["status"]=="proposed"
        assert detail.related_plan["solver_status"]=="optimal_linear_sum_assignment"
    before=len(orchestrator.runs(state.id))
    orchestrator.process_event(event.event_id)
    assert len(orchestrator.runs(state.id))==before
    assert orchestrator.get_trace(event.event_id).event_status=="completed"


def test_missing_local_model_is_explicitly_degraded_without_fabricated_prediction(tmp_path,monkeypatch):
    _,_,plans,state,orchestrator=_system(tmp_path,monkeypatch,model=False)
    event=_event(orchestrator,state,plans)
    orchestrator.process_event(event.event_id)
    detail=orchestrator.get_trace(event.event_id)
    hazard=next(run for run in detail.agents if run.agent_name=="hazard_intelligence")
    assert detail.event_status=="degraded"
    assert hazard.status=="degraded"
    assert hazard.output_summary["model_status"]=="unavailable"
    assert hazard.output_summary["predicted_exposed_building_ids"]==[]
    assert "No prediction was fabricated" in hazard.explanation


def test_flood_escalation_event_detects_new_exposure_and_creates_fresh_proposal(tmp_path,monkeypatch):
    _,scenarios,plans,state,orchestrator=_system(tmp_path,monkeypatch,preset="mild")
    baseline=_event(orchestrator,state,plans);orchestrator.process_event(baseline.event_id)
    changed=scenarios.update_parameters(state.id,ParameterUpdate(rainfall_mm_h=300,river_level_m=5,
        drainage_effectiveness=0,expected_version=state.state_version)).state
    evolved=scenarios.advance(state.id,AdvanceRequest(steps=120,single_step=True,expected_version=changed.state_version)).state
    event=next(item for item in orchestrator.events(state.id) if item.event_type=="simulation_advanced" and item.simulation_state_version==evolved.state_version)
    orchestrator.process_event(event.event_id)
    detail=orchestrator.get_trace(event.event_id)
    hazard=next(run for run in detail.agents if run.agent_name=="hazard_intelligence")
    impact=next(run for run in detail.agents if run.agent_name=="impact_assessment")
    assert len(hazard.output_summary["newly_threatened_building_ids"])>0
    assert detail.trace.evidence["road_changes"] or impact.output_summary["changed_road_or_bridge_ids"]
    assert detail.related_plan is not None and detail.related_plan["status"]=="proposed"
    # The simulation can have many per-tick history rows, but one aggregated
    # outbox envelope bounds coordination work for this multi-step advance.
    matching=[item for item in orchestrator.events(state.id) if item.event_type=="simulation_advanced" and item.simulation_state_version==evolved.state_version]
    assert len(matching)==1


def test_approval_reserves_units_before_the_next_agent_proposal(tmp_path,monkeypatch):
    _,_,plans,state,orchestrator=_system(tmp_path,monkeypatch)
    first=_event(orchestrator,state,plans)
    orchestrator.process_event(first.event_id)
    proposed=plans.by_trigger(first.event_id)
    assert proposed is not None and proposed.status=="proposed"
    assert proposed.missions
    plans.decision(proposed.plan_id,"approved",reason="test commander decision",expected_version=state.state_version)
    events=orchestrator.events(state.id)
    approval=next(item for item in events if item.event_type=="rescue_plan_approved")
    orchestrator.process_event(approval.event_id)
    detail=orchestrator.get_trace(approval.event_id)
    allocation=next(run for run in detail.agents if run.agent_name=="resource_allocation")
    reserved=set(allocation.output_summary["reserved_unit_ids"])
    assert {mission["unit_id"] for mission in proposed.missions}<=reserved
    assert not ({mission["unit_id"] for mission in proposed.missions}&set(allocation.output_summary["assigned_unit_ids"]))
    assert detail.related_plan is None or detail.related_plan["status"]=="proposed"


def test_manual_closure_changes_a_real_route_and_supersedes_old_proposal(tmp_path,monkeypatch):
    path,_,plans,state,orchestrator=_system(tmp_path,monkeypatch,preset="mild")
    first=_event(orchestrator,state,plans);orchestrator.process_event(first.event_id)
    first_detail=orchestrator.get_trace(first.event_id)
    first_routing=next(run for run in first_detail.agents if run.agent_name=="routing").output_summary
    pair=next(item for item in first_routing["reachable_assignments"] if item["unit_id"]=="unit-1" and item["destination_id"]=="building-0-0-0")
    assert "road-ew-1" in pair["route"]["road_ids"]
    with sqlite3.connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT INTO road_closures(scenario_id,epoch,road_id,reason,active) VALUES(?,?,?,'test closure',1)",(state.id,state.epoch,"road-ew-1"))
        db.execute("UPDATE scenario_infrastructure SET revision=revision+1 WHERE scenario_id=? AND epoch=?",(state.id,state.epoch))
        db.commit()
    closure=_event(orchestrator,state,plans,"infrastructure_changed");orchestrator.process_event(closure.event_id)
    changed=next(item for item in next(run for run in orchestrator.get_trace(closure.event_id).agents if run.agent_name=="routing").output_summary["reachable_assignments"] if item["unit_id"]=="unit-1" and item["destination_id"]=="building-0-0-0")
    assert changed["route"]["road_ids"]!=pair["route"]["road_ids"]
    assert "road-ew-1" not in changed["route"]["road_ids"]
    assert plans.by_trigger(first.event_id).status=="superseded"


def test_closure_during_proposal_save_rejects_stale_candidate(tmp_path,monkeypatch):
    path,_,plans,state,orchestrator=_system(tmp_path,monkeypatch)
    event=_event(orchestrator,state,plans)
    original_save=plans.save
    def close_before_commit(plan):
        with sqlite3.connect(path) as db:
            db.execute("UPDATE scenario_infrastructure SET revision=revision+1 WHERE scenario_id=? AND epoch=?",(state.id,state.epoch))
        return original_save(plan)
    monkeypatch.setattr(plans,"save",close_before_commit)
    orchestrator.process_event(event.event_id)
    detail=orchestrator.get_trace(event.event_id)
    assert detail.event_status=="failed"
    assert any(run.agent_name=="commander_strategy" and run.status=="failed" for run in detail.agents)
    assert plans.by_trigger(event.event_id) is None


def test_stale_infrastructure_event_is_superseded_before_any_agent_runs(tmp_path,monkeypatch):
    path,_,plans,state,orchestrator=_system(tmp_path,monkeypatch)
    event=_event(orchestrator,state,plans)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE scenario_infrastructure SET revision=revision+1 WHERE scenario_id=? AND epoch=?",(state.id,state.epoch))
    orchestrator.process_event(event.event_id)
    detail=orchestrator.get_trace(event.event_id)
    assert detail.event_status=="superseded"
    assert all(run.status=="superseded" for run in detail.agents)
    assert detail.trace.status=="superseded"


def test_restart_recovery_replays_pending_event_and_duplicate_workers_are_safe(tmp_path,monkeypatch):
    _,_,plans,state,orchestrator=_system(tmp_path,monkeypatch)
    event=_event(orchestrator,state,plans)
    restarted=AgentOrchestrator(orchestrator.scenarios,plans)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda worker:worker.process_event(event.event_id),(orchestrator,restarted)))
    detail=restarted.get_trace(event.event_id)
    assert detail.event_status=="completed"
    assert len(detail.agents)==6
    assert detail.attempts==1


def test_replay_does_not_enqueue_or_run_operational_agent_events(tmp_path,monkeypatch):
    _,scenarios,plans,state,orchestrator=_system(tmp_path,monkeypatch)
    before=len(orchestrator.events(state.id))
    scenarios.replay(state.id,state.tick)
    assert len(orchestrator.events(state.id))==before


def test_reset_uses_new_epoch_and_historical_reservations_remain_epoch_scoped(tmp_path,monkeypatch):
    _,scenarios,plans,state,orchestrator=_system(tmp_path,monkeypatch)
    prior=_event(orchestrator,state,plans)
    reset=scenarios.reset(state.id,state.state_version).state
    assert reset.epoch==state.epoch+1
    current=[event for event in orchestrator.events(state.id) if event.event_type=="scenario_reset"]
    assert current and current[0].scenario_epoch==reset.epoch
    assert prior.scenario_epoch==state.epoch
    assert plans.reserved_units(state.id,reset.epoch)==set()


def test_repeated_ticks_keep_one_current_trigger_and_audit_superseded_pending_events(tmp_path,monkeypatch):
    _,scenarios,plans,state,orchestrator=_system(tmp_path,monkeypatch)
    advanced=scenarios.advance(state.id,AdvanceRequest(steps=4,single_step=True,expected_version=state.state_version)).state
    class Background:
        def __init__(self):self.ids=[]
        def add_task(self,func,event_id):self.ids.append(event_id)
    background=Background()
    orchestrator.schedule_pending(background,state.id,advanced.state_version,advanced.epoch)
    assert len(background.ids)==1
    selected=orchestrator.get_trace(background.ids[0])
    assert selected.event.event_type=="simulation_advanced"
    assert selected.event_status=="pending"
    prior=[item for item in orchestrator.events(state.id) if item.event_type=="scenario_created"]
    assert orchestrator.get_trace(prior[0].event_id).event_status=="superseded"
    assert orchestrator.get_trace(prior[0].event_id).trace.evidence["superseded_by_state_version"]==advanced.state_version


def test_out_of_support_ml_labels_are_excluded_and_disclosed_in_agent_trace(tmp_path,monkeypatch):
    _,_,plans,state,orchestrator=_system(tmp_path,monkeypatch)
    city=generate_city(state.seed)
    predictions=SimpleNamespace(model_version="synthetic-v1",reliability_status="available",calibration_status="adopted",reliability_warnings=[],predictions=[
        SimpleNamespace(building_id=city.buildings[0].id,predicted_future_exposed=True,uncalibrated_model_score=.9,distribution_support_status="outside_observed_support"),
        SimpleNamespace(building_id=city.buildings[1].id,predicted_future_exposed=True,uncalibrated_model_score=.8,distribution_support_status="within_observed_support"),
    ])
    monkeypatch.setattr("app.agents.predictions",lambda _scenario_id:predictions)
    event=_event(orchestrator,state,plans)
    orchestrator.process_event(event.event_id)
    detail=orchestrator.get_trace(event.event_id)
    hazard=next(run for run in detail.agents if run.agent_name=="hazard_intelligence")
    assert hazard.status=="degraded"
    assert hazard.output_summary["predicted_exposed_building_ids"]==[city.buildings[1].id]
    assert detail.trace.evidence["distribution_support_counts"]["outside_observed_support"]==1
    assert any("excluded from forecast-based planning eligibility" in warning for warning in detail.trace.evidence["model_reliability_warnings"])
