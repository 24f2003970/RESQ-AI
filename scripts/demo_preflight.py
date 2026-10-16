"""Read-only local RESQ-AI readiness diagnostic; HTTP probes use loopback."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
API = os.getenv("RESQ_API_URL", "http://127.0.0.1:8000").rstrip("/")
WEB = os.getenv("RESQ_WEB_URL", "http://127.0.0.1:5173").rstrip("/")
DB_PATH = Path(os.getenv("RESQ_DB_PATH", str(BACKEND / "data" / "resq.sqlite3")))


def check(name: str, ok: bool | None, detail: str) -> dict:
    return {"name": name, "status": "PASS" if ok is True else "FAIL" if ok is False else "WARN", "detail": detail}


def get_json(url: str) -> tuple[int, object]:
    with urllib.request.urlopen(url, timeout=2) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def get_status(url: str) -> int:
    with urllib.request.urlopen(url, timeout=2) as response:
        return response.status


def read_only_schema() -> tuple[bool | None, str]:
    if not DB_PATH.exists():
        return None, "No local database exists yet; startup initializes it."
    try:
        with sqlite3.connect(DB_PATH.resolve().as_uri() + "?mode=ro", uri=True, timeout=2) as db:
            names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {"scenarios", "events", "checkpoints", "agent_event_outbox", "missions", "unit_resources"}
        missing = sorted(required - names)
        return (not missing, "Required tables are present." if not missing else "Missing tables: " + ", ".join(missing))
    except sqlite3.Error as exc:
        return False, f"Database could not be read safely ({type(exc).__name__})."


def run() -> dict:
    started = time.perf_counter()
    checks = []
    checks.append(check("Python runtime", sys.version_info[:2] == (3, 12), f"Detected {platform.python_version()}; requires 3.12."))
    for package in ("fastapi", "uvicorn", "numpy", "scipy", "scikit-learn", "networkx", "joblib", "pydantic"):
        try:
            checks.append(check("Python dependency: " + package, True, importlib.metadata.version(package)))
        except importlib.metadata.PackageNotFoundError:
            checks.append(check("Python dependency: " + package, False, "Not installed in this interpreter."))
    checks.append(check("Frontend dependencies", (FRONTEND / "node_modules").is_dir(), "frontend/node_modules is present." if (FRONTEND / "node_modules").is_dir() else "Run scripts/setup-resq-ai.ps1."))
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=3, check=True)
        version = result.stdout.strip().lstrip("v").split(".")
        node_ok = (int(version[0]), int(version[1])) >= (22, 12)
        checks.append(check("Node runtime", node_ok, f"Detected v{result.stdout.strip().lstrip('v')}; requires 22.12 or newer."))
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        checks.append(check("Node runtime", False, "Node.js is unavailable or its version could not be read."))

    model = BACKEND / "ml_artifacts" / "flood_exposure_v1.joblib"
    metadata = BACKEND / "ml_artifacts" / "model_metadata.json"
    try:
        data = json.loads(metadata.read_text(encoding="utf-8"))
        digest = hashlib.sha256(model.read_bytes()).hexdigest()
        valid = digest == data.get("artifact_sha256")
        checks.append(check("Trained model artifact", valid, "Checksum matches training metadata." if valid else "Missing artifact or checksum mismatch."))
    except (OSError, json.JSONDecodeError):
        checks.append(check("Trained model artifact", False, "Artifact or model metadata is missing or invalid."))
    for label, path in (("Dataset metadata", BACKEND / "ml_artifacts" / "dataset_metadata.json"),
                        ("Evaluation metadata", BACKEND / "ml_artifacts" / "evaluation.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
            checks.append(check(label, True, "Local metadata is readable."))
        except (OSError, json.JSONDecodeError):
            checks.append(check(label, False, "Local metadata is missing or invalid."))

    live = False
    try:
        _, health = get_json(API + "/api/v1/health")
        live = health.get("status") == "ok"
        checks.append(check("Backend API health", live, "Local API responded."))
    except (OSError, ValueError, urllib.error.URLError) as exc:
        checks.append(check("Backend API health", False, f"Unavailable ({type(exc).__name__}); start it before preflight."))
    if live:
        for label, path, valid in (("City/scenario endpoints", "/api/v1/city/state", lambda value: bool(value.get("buildings"))),
                                   ("Agent infrastructure", "/api/v1/agents/registry", lambda value: isinstance(value,list) and len(value)==6),
                                   ("Model readiness", "/api/v1/ml/model", lambda value: value.get("status")=="ready")):
            try:
                _, payload = get_json(API + path)
                checks.append(check(label, bool(valid(payload)), "Local API contract responded."))
            except (OSError, ValueError, urllib.error.URLError) as exc:
                checks.append(check(label, False, f"Endpoint failed ({type(exc).__name__})."))
        try:
            _, active = get_json(API + "/api/v1/scenarios/active")
            sid = active["state"]["id"]
            for label, suffix in (("Agent status", "agent-status"), ("Rescue planning availability", "missions/units"), ("Mission API availability", "missions")):
                try:
                    get_json(f"{API}/api/v1/scenarios/{sid}/{suffix}")
                    checks.append(check(label, True, "Active scenario endpoint responded without mutation."))
                except (OSError, ValueError, urllib.error.URLError) as exc:
                    checks.append(check(label, False, f"Endpoint failed ({type(exc).__name__})."))
        except (OSError, ValueError, KeyError, urllib.error.URLError) as exc:
            checks.append(check("Active scenario", False, f"Unavailable ({type(exc).__name__})."))
    schema_ok, schema_detail = read_only_schema()
    checks.append(check("SQLite schema readiness", schema_ok, schema_detail))
    try:
        get_status(WEB)
        checks.append(check("Local frontend accessibility", True, "Frontend responded on loopback."))
    except (OSError, ValueError, urllib.error.URLError) as exc:
        checks.append(check("Local frontend accessibility", False, f"Unavailable ({type(exc).__name__})."))
    local = API.startswith(("http://127.0.0.1", "http://localhost")) and WEB.startswith(("http://127.0.0.1", "http://localhost"))
    try:
        vite_config=(FRONTEND/"vite.config.ts").read_text(encoding="utf-8")
        cors_config=(BACKEND/"app"/"config.py").read_text(encoding="utf-8")
        web_port=urlparse(WEB).port
        proxy_matches=f'"/api": "{API}"' in vite_config or f'"/api": "{API}/"' in vite_config
        cors_matches=f'http://127.0.0.1:{web_port}' in cors_config or f'http://localhost:{web_port}' in cors_config
        consistent=local and proxy_matches and cors_matches
        detail="Loopback API/frontend URLs agree with the Vite proxy and configured CORS origin." if consistent else "Loopback URLs, Vite API proxy and configured CORS origin do not agree."
    except (OSError, ValueError):
        consistent=False
        detail="Could not read the local Vite proxy or CORS configuration."
    checks.append(check("Runtime configuration", consistent, detail))
    status = "FAIL" if any(row["status"] == "FAIL" for row in checks) else "WARN" if any(row["status"] == "WARN" for row in checks) else "PASS"
    return {"schema_version":1,"generated_at_utc":datetime.now(timezone.utc).isoformat(),"duration_ms":round((time.perf_counter()-started)*1000,3),"status":status,"checks":checks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, help="Write a redacted JSON diagnostic report.")
    args = parser.parse_args()
    report=run()
    for item in report["checks"]: print(f"{item['status']:<4} {item['name']}: {item['detail']}")
    print("Overall: " + report["status"])
    if args.export:
        args.export.parent.mkdir(parents=True,exist_ok=True)
        args.export.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return 1 if report["status"]=="FAIL" else 0


if __name__=="__main__":
    raise SystemExit(main())
