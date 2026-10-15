import json
import logging
import time
import uuid
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .city_service import generate_city
from .config import settings
from .schemas import Building, CityState, Health, ScenarioMetadata

logger = logging.getLogger("resq")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())

app = FastAPI(title="RESQ-AI Local API", version="0.2.0", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins),
                   allow_methods=["GET"], allow_headers=["Content-Type"])


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
    return Health(status="ok", service="resq-ai", version="0.2.0", mode="local")


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
