import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .city_service import generate_city
from .config import settings
from .ml_service import ModelUnavailable, dataset_info, evaluation_info, feature_info, model_info, predictions
from .scenarios import ScenarioError, store
from .rescue import PlanStore, RescuePlan, generate_plan
from .agents import AgentOrchestrator
from .agent_contracts import (
    AgentDashboard, AgentDefinition, AgentEventAccepted, AgentEventEnvelope,
    AgentRunRecord, AgentTraceDetail, persist_agent_event,
)
from .experiments import ExperimentCreate, ExperimentRecord, ExperimentRepository, ExperimentRunner
from .schemas import (
    AdvanceRequest, Building, CityState, Health, ParameterUpdate, ScenarioCreate,
    MLDatasetInfo, MLEvaluationReport, MLFeatureInfo, MLModelInfo, ScenarioEnvelope,
    ScenarioMetadata, ScenarioPredictionSet, SimulationEvent, VersionRequest,
    RescuePlanDecision, RoadClosureRequest, RescuePlanModification,
)

logger = logging.getLogger("resq")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())

rescue_plans = PlanStore(store.path)
agent_orchestrator = AgentOrchestrator(store,rescue_plans)
experiment_repository = ExperimentRepository(store.path.with_name("experiments.sqlite3"))
experiment_runner = ExperimentRunner(experiment_repository)

@asynccontextmanager
async def lifespan(_app):
    agent_orchestrator.recover()
    yield

app = FastAPI(title="RESQ-AI Local API", version="0.4.0", docs_url=None, redoc_url=None, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins),
                   allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type", "Idempotency-Key"])


@app.middleware("http")
async def request_log(request: Request, call_next):
    request_id = uuid.uuid4().hex
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(json.dumps({"event": "request_failed", "request_id": request_id}))
        response = JSONResponse(status_code=500, content={"error": {"code": "internal_error",
            "message": "The local service could not complete this request.", "request_id": request_id}})
    response.headers["X-Request-ID"] = request_id
    logger.info(json.dumps({"event": "http_request", "method": request.method, "path": request.url.path,
                           "status": response.status_code, "request_id": request_id,
                           "elapsed_ms": round((time.perf_counter() - start) * 1000, 2)}))
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code,
                        content={"error": {"code": "not_found" if exc.status_code == 404 else "request_error",
                                           "message": str(exc.detail)}})


@app.get("/api/v1/health", response_model=Health)
def health():
    return Health(status="ok", service="resq-ai", version="0.4.0", mode="local")


@app.get("/api/v1/city/state", response_model=CityState)
def city_state(seed: int = Query(default=settings.city_seed, ge=0, le=2_147_483_647)):
    return generate_city(seed)


@app.get("/api/v1/scenarios/default", response_model=ScenarioMetadata)
def default_scenario():
    return generate_city(settings.city_seed).scenario


@app.get("/api/v1/city/buildings/{building_id}", response_model=Building)
def building_detail(building_id: str):
    result = next((b for b in generate_city(settings.city_seed).buildings if b.id == building_id), None)
    if result is None:
        raise HTTPException(404, "This building does not exist in the current city.")
    return result


def _scenario_call(action):
    try:
        return action()
    except ScenarioError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@app.get("/api/v1/scenarios/active", response_model=ScenarioEnvelope)
def active_scenario():
    return _scenario_call(lambda: store.get(store.active_id()))


@app.post("/api/v1/scenarios", response_model=ScenarioEnvelope, status_code=201)
def create_scenario(request: ScenarioCreate, background_tasks: BackgroundTasks, idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128)):
    result=_scenario_call(lambda: store.create(request, idempotency_key))
    agent_orchestrator.schedule_pending(background_tasks,result.state.id,result.state.state_version,result.state.epoch)
    return result


@app.get("/api/v1/scenarios/{scenario_id}", response_model=ScenarioEnvelope)
def get_scenario(scenario_id: str):
    return _scenario_call(lambda: store.get(scenario_id))


@app.patch("/api/v1/scenarios/{scenario_id}/parameters", response_model=ScenarioEnvelope)
def update_scenario_parameters(scenario_id: str, request: ParameterUpdate, background_tasks: BackgroundTasks):
    result=_scenario_call(lambda: store.update_parameters(scenario_id, request))
    agent_orchestrator.schedule_pending(background_tasks,scenario_id,result.state.state_version,result.state.epoch)
    return result


@app.post("/api/v1/scenarios/{scenario_id}/start", response_model=ScenarioEnvelope)
def start_scenario(scenario_id: str, request: VersionRequest):
    return _scenario_call(lambda: store.transition(scenario_id, request.expected_version, "start"))


@app.post("/api/v1/scenarios/{scenario_id}/pause", response_model=ScenarioEnvelope)
def pause_scenario(scenario_id: str, request: VersionRequest):
    return _scenario_call(lambda: store.transition(scenario_id, request.expected_version, "pause"))


@app.post("/api/v1/scenarios/{scenario_id}/resume", response_model=ScenarioEnvelope)
def resume_scenario(scenario_id: str, request: VersionRequest):
    return _scenario_call(lambda: store.transition(scenario_id, request.expected_version, "resume"))


@app.post("/api/v1/scenarios/{scenario_id}/advance", response_model=ScenarioEnvelope)
def advance_scenario(scenario_id: str, request: AdvanceRequest, background_tasks: BackgroundTasks):
    result=_scenario_call(lambda: store.advance(scenario_id, request))
    agent_orchestrator.schedule_pending(background_tasks,scenario_id,result.state.state_version,result.state.epoch)
    return result


@app.post("/api/v1/scenarios/{scenario_id}/reset", response_model=ScenarioEnvelope)
def reset_scenario(scenario_id: str, request: VersionRequest, background_tasks: BackgroundTasks):
    result=_scenario_call(lambda: store.reset(scenario_id, request.expected_version))
    agent_orchestrator.schedule_pending(background_tasks,scenario_id,result.state.state_version,result.state.epoch)
    return result


@app.get("/api/v1/scenarios/{scenario_id}/events", response_model=list[SimulationEvent])
def scenario_events(scenario_id: str):
    return _scenario_call(lambda: store.events(scenario_id))


@app.get("/api/v1/scenarios/{scenario_id}/replay/{tick}", response_model=ScenarioEnvelope)
def replay_scenario(scenario_id: str, tick: int):
    return _scenario_call(lambda: store.replay(scenario_id, tick))


@app.get("/api/v1/scenarios/{scenario_id}/snapshots", response_model=list[dict])
def scenario_snapshots(scenario_id: str):
    return _scenario_call(lambda: store.snapshots(scenario_id))


@app.get("/api/v1/ml/model", response_model=MLModelInfo)
def ml_model_info():
    return model_info()


@app.get("/api/v1/ml/dataset", response_model=MLDatasetInfo)
def ml_dataset_info():
    try:
        return dataset_info()
    except ModelUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/api/v1/ml/evaluation", response_model=MLEvaluationReport)
def ml_evaluation_info():
    try:
        return evaluation_info()
    except ModelUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/api/v1/ml/features", response_model=list[MLFeatureInfo])
def ml_feature_info():
    return feature_info()


@app.get("/api/v1/scenarios/{scenario_id}/predictions", response_model=ScenarioPredictionSet)
def scenario_predictions(scenario_id: str):
    availability = model_info()
    if availability.status != "ready":
        raise HTTPException(503, availability.unavailable_reason or "The local model is unavailable.")
    try:
        return _scenario_call(lambda: predictions(scenario_id))
    except ModelUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/api/v1/scenarios/{scenario_id}/predictions/{building_id}", response_model=ScenarioPredictionSet)
def building_prediction(scenario_id: str, building_id: str):
    availability = model_info()
    if availability.status != "ready":
        raise HTTPException(503, availability.unavailable_reason or "The local model is unavailable.")
    try:
        return _scenario_call(lambda: predictions(scenario_id, building_id))
    except ModelUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/v1/scenarios/{scenario_id}/rescue-plans", status_code=201, response_model=RescuePlan)
def create_rescue_plan(scenario_id: str):
    envelope = _scenario_call(lambda: store.get(scenario_id))
    try:
        prediction_set = predictions(scenario_id)
        infrastructure_revision, closures = rescue_plans.infrastructure(scenario_id, envelope.state.epoch)
        reserved = rescue_plans.reserved_units(scenario_id, envelope.state.epoch)
        plan = generate_plan(generate_city(envelope.state.seed), envelope.state, prediction_set, closures,
                             infrastructure_revision=infrastructure_revision, reserved_unit_ids=reserved)
        try:
            return rescue_plans.save(plan)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
    except ModelUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/api/v1/rescue-plans/{plan_id}", response_model=RescuePlan)
def get_rescue_plan(plan_id: str):
    plan = rescue_plans.get(plan_id)
    if plan is None:
        raise HTTPException(404, "Rescue plan does not exist.")
    return plan


@app.post("/api/v1/rescue-plans/{plan_id}/decision", response_model=RescuePlan)
def decide_rescue_plan(plan_id: str, decision: RescuePlanDecision, background_tasks: BackgroundTasks):
    try:
        plan=rescue_plans.decision(plan_id, decision.action, decision.reason, decision.expected_version)
        agent_orchestrator.schedule_pending(background_tasks,plan.scenario_id,plan.scenario_version,plan.scenario_epoch)
        return plan
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.patch("/api/v1/rescue-plans/{plan_id}/assignments", response_model=RescuePlan)
def modify_rescue_assignments(plan_id: str, request: RescuePlanModification):
    try:
        return rescue_plans.modify(plan_id, request.assignments, request.expected_version)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/v1/scenarios/{scenario_id}/road-closures")
def close_road(scenario_id: str, request: RoadClosureRequest, background_tasks: BackgroundTasks):
    _scenario_call(lambda: store.get(scenario_id))
    road_id, reason = request.road_id, request.reason
    city = generate_city(settings.city_seed)
    if road_id not in {road.id for road in city.roads}:
        raise HTTPException(422, "Unknown road ID.")
    import sqlite3
    with sqlite3.connect(store.path, timeout=10, isolation_level=None) as db:
        db.execute("BEGIN IMMEDIATE")
        scenario_row=db.execute("SELECT epoch,tick,state_version FROM scenarios WHERE id=?",(scenario_id,)).fetchone()
        if scenario_row is None:
            db.rollback();raise HTTPException(404,"Scenario does not exist.")
        epoch=scenario_row[0]
        db.execute("INSERT OR IGNORE INTO scenario_infrastructure(scenario_id,epoch,revision) VALUES(?,?,0)",(scenario_id,epoch))
        db.execute("INSERT INTO road_closures(scenario_id,epoch,road_id,reason,active) VALUES(?,?,?,?,1) ON CONFLICT(scenario_id,epoch,road_id) DO UPDATE SET reason=excluded.reason,active=1", (scenario_id, epoch, road_id, reason))
        db.execute("UPDATE scenario_infrastructure SET revision=revision+1 WHERE scenario_id=? AND epoch=?",(scenario_id,epoch))
        revision=db.execute("SELECT revision FROM scenario_infrastructure WHERE scenario_id=? AND epoch=?",(scenario_id,epoch)).fetchone()[0]
        persist_agent_event(db,event_type="infrastructure_changed",scenario_id=scenario_id,scenario_epoch=epoch,
            simulation_tick=scenario_row[1],state_version=scenario_row[2],infrastructure_revision=revision,
            source_module="manual_closure_api",payload={"action":"close","road_id":road_id,"reason":reason})
        stale = db.execute("SELECT plan_id FROM rescue_plans WHERE scenario_id=? AND status='proposed'", (scenario_id,)).fetchall()
        db.execute("UPDATE rescue_plans SET status='superseded' WHERE scenario_id=? AND status='proposed'", (scenario_id,))
        for (plan_id,) in stale:
            db.execute("INSERT INTO rescue_events(plan_id,event_type,detail,created_at) VALUES(?,?,?,CURRENT_TIMESTAMP)", (plan_id,"superseded",json.dumps({"reason":"Manual road closure changed route accessibility.","road_id":road_id})))
        db.execute("INSERT INTO rescue_events(plan_id,event_type,detail,created_at) VALUES(?,?,?,CURRENT_TIMESTAMP)", ("scenario:"+scenario_id,"road_manually_closed",json.dumps({"road_id":road_id,"reason":reason})))
        db.commit()
    _,closures=rescue_plans.infrastructure(scenario_id,epoch)
    agent_orchestrator.schedule_pending(background_tasks,scenario_id,scenario_row[2],epoch)
    return {"scenario_id":scenario_id,"road_id":road_id,"status":"manually_blocked","reason":reason,"infrastructure_revision":revision,"closures":closures}


@app.delete("/api/v1/scenarios/{scenario_id}/road-closures/{road_id}")
def reopen_road(scenario_id: str, road_id: str, background_tasks: BackgroundTasks):
    _scenario_call(lambda: store.get(scenario_id))
    import sqlite3
    with sqlite3.connect(store.path, timeout=10, isolation_level=None) as db:
        db.execute("BEGIN IMMEDIATE")
        scenario_row=db.execute("SELECT epoch,tick,state_version FROM scenarios WHERE id=?",(scenario_id,)).fetchone()
        if scenario_row is None:
            db.rollback();raise HTTPException(404,"Scenario does not exist.")
        epoch=scenario_row[0]
        db.execute("INSERT OR IGNORE INTO scenario_infrastructure(scenario_id,epoch,revision) VALUES(?,?,0)",(scenario_id,epoch))
        cursor = db.execute("UPDATE road_closures SET active=0 WHERE scenario_id=? AND epoch=? AND road_id=? AND active=1", (scenario_id, epoch, road_id))
        if not cursor.rowcount:
            db.rollback()
            raise HTTPException(404, "No active manual closure exists for this road.")
        db.execute("UPDATE scenario_infrastructure SET revision=revision+1 WHERE scenario_id=? AND epoch=?",(scenario_id,epoch))
        revision=db.execute("SELECT revision FROM scenario_infrastructure WHERE scenario_id=? AND epoch=?",(scenario_id,epoch)).fetchone()[0]
        persist_agent_event(db,event_type="infrastructure_changed",scenario_id=scenario_id,scenario_epoch=epoch,
            simulation_tick=scenario_row[1],state_version=scenario_row[2],infrastructure_revision=revision,
            source_module="manual_closure_api",payload={"action":"reopen","road_id":road_id})
        stale = db.execute("SELECT plan_id FROM rescue_plans WHERE scenario_id=? AND status='proposed'", (scenario_id,)).fetchall()
        db.execute("UPDATE rescue_plans SET status='superseded' WHERE scenario_id=? AND status='proposed'", (scenario_id,))
        for (plan_id,) in stale:
            db.execute("INSERT INTO rescue_events(plan_id,event_type,detail,created_at) VALUES(?,?,?,CURRENT_TIMESTAMP)", (plan_id,"superseded",json.dumps({"reason":"Road closure was removed; route snapshot changed.","road_id":road_id})))
        db.execute("INSERT INTO rescue_events(plan_id,event_type,detail,created_at) VALUES(?,?,?,CURRENT_TIMESTAMP)", ("scenario:"+scenario_id,"road_reopened",json.dumps({"road_id":road_id})))
        db.commit()
    revision,closures=rescue_plans.infrastructure(scenario_id,epoch)
    agent_orchestrator.schedule_pending(background_tasks,scenario_id,scenario_row[2],epoch)
    return {"scenario_id":scenario_id,"road_id":road_id,"status":"reopened","infrastructure_revision":revision,"closures":closures}


@app.get("/api/v1/agents/registry",response_model=list[AgentDefinition])
def agent_registry():
    from .agents import AGENTS
    return AGENTS


@app.get("/api/v1/scenarios/{scenario_id}/agent-status",response_model=AgentDashboard)
def agent_status(scenario_id:str):
    envelope=_scenario_call(lambda:store.get(scenario_id))
    return agent_orchestrator.dashboard(scenario_id,envelope.state)


@app.get("/api/v1/scenarios/{scenario_id}/recommendations/latest",response_model=RescuePlan | None)
def latest_agent_recommendation(scenario_id:str):
    envelope=_scenario_call(lambda:store.get(scenario_id))
    return rescue_plans.latest_valid(scenario_id,envelope.state)


@app.get("/api/v1/scenarios/{scenario_id}/agent-events",response_model=list[AgentEventEnvelope])
def agent_events(scenario_id:str,limit:int=50):
    _scenario_call(lambda:store.get(scenario_id))
    if limit<1 or limit>200:raise HTTPException(422,"Event limit must be between 1 and 200.")
    return agent_orchestrator.events(scenario_id,limit)


@app.get("/api/v1/scenarios/{scenario_id}/agent-runs",response_model=list[AgentRunRecord])
def agent_runs(scenario_id:str,limit:int=100):
    _scenario_call(lambda:store.get(scenario_id))
    if limit<1 or limit>250:raise HTTPException(422,"Run limit must be between 1 and 250.")
    return agent_orchestrator.runs(scenario_id,limit)


@app.get("/api/v1/agent-traces/{event_id}",response_model=AgentTraceDetail)
def agent_trace(event_id:str):
    trace=agent_orchestrator.get_trace(event_id)
    if trace is None:raise HTTPException(404,"Agent decision trace does not exist.")
    return trace


@app.post("/api/v1/scenarios/{scenario_id}/intelligence-assessments",status_code=202,response_model=AgentEventAccepted)
def run_intelligence_assessment(scenario_id:str,background_tasks:BackgroundTasks):
    envelope=_scenario_call(lambda:store.get(scenario_id))
    revision,closures=rescue_plans.infrastructure(scenario_id,envelope.state.epoch)
    event=agent_orchestrator.enqueue(event_type="manual_assessment",scenario_id=scenario_id,state=envelope.state,
        infrastructure_revision=revision,source_module="commander_manual_assessment",
        payload={"manual_request":True,"active_manual_closures":closures})
    background_tasks.add_task(agent_orchestrator.process_event,event.event_id)
    return AgentEventAccepted(event_id=event.event_id,status="pending",scenario_id=scenario_id,
        scenario_epoch=envelope.state.epoch,simulation_tick=envelope.state.tick,
        simulation_state_version=envelope.state.state_version)


@app.post("/api/v1/agent-events/{event_id}/retry",response_model=AgentEventAccepted)
def retry_agent_event(event_id:str,background_tasks:BackgroundTasks):
    with __import__("sqlite3").connect(store.path) as db:
        row=db.execute("SELECT envelope_json,status,attempts FROM agent_event_outbox WHERE event_id=?",(event_id,)).fetchone()
    if not row:raise HTTPException(404,"Agent event does not exist.")
    if row[1] not in ("failed","pending") or row[2]>=3:raise HTTPException(409,"This event is not retryable or reached its three-attempt limit.")
    envelope=AgentEventEnvelope.model_validate_json(row[0])
    background_tasks.add_task(agent_orchestrator.retry,event_id)
    return AgentEventAccepted(event_id=event_id,status="pending",scenario_id=envelope.scenario_id,
        scenario_epoch=envelope.scenario_epoch,simulation_tick=envelope.simulation_tick,
        simulation_state_version=envelope.simulation_state_version)


@app.post("/api/v1/scenarios/{scenario_id}/experiments",status_code=202,response_model=ExperimentRecord)
def create_scenario_experiment(scenario_id: str, request: ExperimentCreate, background_tasks: BackgroundTasks):
    if request.base_scenario_id != scenario_id:
        raise HTTPException(422, "Experiment base_scenario_id must match the scenario in the URL.")
    envelope = _scenario_call(lambda: store.get(scenario_id))
    try:
        record = experiment_repository.create(request, envelope.state)
    except ScenarioError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    background_tasks.add_task(experiment_runner.run, record.experiment_id)
    return record


@app.get("/api/v1/scenarios/{scenario_id}/experiments",response_model=list[ExperimentRecord])
def list_scenario_experiments(scenario_id: str, limit: int = Query(default=20, ge=1, le=100)):
    _scenario_call(lambda: store.get(scenario_id))
    return experiment_repository.list(scenario_id, limit)


@app.get("/api/v1/scenario-experiments/{experiment_id}",response_model=ExperimentRecord)
def get_scenario_experiment(experiment_id: str):
    record = experiment_repository.get(experiment_id)
    if record is None:
        raise HTTPException(404, "Scenario experiment does not exist.")
    return record


@app.post("/api/v1/scenario-experiments/{experiment_id}/cancel",response_model=ExperimentRecord)
def cancel_scenario_experiment(experiment_id: str):
    record = experiment_repository.cancel(experiment_id)
    if record is None:
        raise HTTPException(404, "Scenario experiment does not exist.")
    return record
