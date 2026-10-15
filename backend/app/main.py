import json
import logging
import time
import uuid
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .city_service import generate_city
from .config import settings
from .scenarios import ScenarioError, store
from .schemas import (
    AdvanceRequest, Building, CityState, Health, ParameterUpdate, ScenarioCreate,
    ScenarioEnvelope, ScenarioMetadata, SimulationEvent, VersionRequest,
)

logger = logging.getLogger("resq")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())

app = FastAPI(title="RESQ-AI Local API", version="0.3.0", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins),
                   allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type", "Idempotency-Key"])


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
    return Health(status="ok", service="resq-ai", version="0.3.0", mode="local")


@app.get("/api/v1/city/state", response_model=CityState)
def city_state():
    return generate_city(settings.city_seed)


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
def create_scenario(request: ScenarioCreate, idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128)):
    return _scenario_call(lambda: store.create(request, idempotency_key))


@app.get("/api/v1/scenarios/{scenario_id}", response_model=ScenarioEnvelope)
def get_scenario(scenario_id: str):
    return _scenario_call(lambda: store.get(scenario_id))


@app.patch("/api/v1/scenarios/{scenario_id}/parameters", response_model=ScenarioEnvelope)
def update_scenario_parameters(scenario_id: str, request: ParameterUpdate):
    return _scenario_call(lambda: store.update_parameters(scenario_id, request))


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
def advance_scenario(scenario_id: str, request: AdvanceRequest):
    return _scenario_call(lambda: store.advance(scenario_id, request))


@app.post("/api/v1/scenarios/{scenario_id}/reset", response_model=ScenarioEnvelope)
def reset_scenario(scenario_id: str, request: VersionRequest):
    return _scenario_call(lambda: store.reset(scenario_id, request.expected_version))


@app.get("/api/v1/scenarios/{scenario_id}/events", response_model=list[SimulationEvent])
def scenario_events(scenario_id: str):
    return _scenario_call(lambda: store.events(scenario_id))


@app.get("/api/v1/scenarios/{scenario_id}/replay/{tick}", response_model=ScenarioEnvelope)
def replay_scenario(scenario_id: str, tick: int):
    return _scenario_call(lambda: store.replay(scenario_id, tick))


@app.get("/api/v1/scenarios/{scenario_id}/snapshots", response_model=list[dict])
def scenario_snapshots(scenario_id: str):
    return _scenario_call(lambda: store.snapshots(scenario_id))
