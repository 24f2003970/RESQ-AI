# RESQ-AI

**Predict. Simulate. Prioritize. Respond. Replan.**

RESQ-AI is an offline-first disaster response command center for a deterministic fictional city. It combines a stateful flood simulation, a locally trained risk classifier, explainable coordination agents, rescue route and resource planning, and an interactive 3D Digital Twin. The system is a decision-support prototype for a two-student Innotech hackathon team; it is not an operational warning or dispatch system.

## What the demonstration will show

1. Load the same seed-based city and scenario on every run.
2. Increase rainfall and river stage, then inspect simulated inundation and affected assets.
3. Compare the local classifier with a transparent rule baseline and inspect its limitations.
4. Prioritize zones, assign available rescue units, and display routes on the city.
5. Block a bridge or road and watch the event-driven plan recalculate.
6. Review the proposed actions, approve or reject them, and replay the decision timeline.

Every displayed metric must come from backend state or a recorded experiment. Simulated data, assumptions, and model results will be labeled as such. No hosted AI inference or external AI API key is part of the design. Once dependencies and any optional data are installed, the application must run locally without network access.

## Planned stack

- **Web:** React, TypeScript, Vite, Tailwind CSS, shadcn/ui, Framer Motion, React Three Fiber, Three.js, Recharts.
- **Service:** Python, FastAPI, Pydantic, SQLite, local REST and WebSocket endpoints.
- **Model and algorithms:** scikit-learn, NumPy, pandas, joblib, NetworkX; simple deterministic algorithms first. OR-Tools is optional and must justify its added setup cost.
- **Verification:** pytest, TypeScript type checks and linting, component and integration checks, deterministic simulation scenarios.

The backend owns scenario state, simulation steps, predictions, agent decisions, assignments, and event history. The 3D scene renders a read-only projection of that state and sends user commands back through the API.

## Current implementation — Part 2

The local full-stack foundation renders backend-generated city geometry and inventory. Command Center and Digital Twin Studio include building selection, an API-backed inspector, camera reset/focus/orbit/zoom/pan, map layers, snapshot export, and a building-inventory fallback. The other three routes explain their future scope. Connection status is based on successful local API requests, with retries and a stale-snapshot warning when the service disconnects.

The seeded baseline contains 72 buildings, four districts, ten road corridors, six bridge crossings, one hospital, one shelter, two parks, and five response units. No flood simulation, model training, agent decisions, or rescue optimization is implemented in this part.

## Repository map

```text
backend/
  app/             # Configuration, Pydantic schemas, seed service, FastAPI routes
  tests/           # Determinism, relationships, schemas, endpoints and CORS
  export_contract.py
  requirements.txt # Exact installed dependency versions
frontend/
  src/api/         # Generated OpenAPI types and JSON-schema payload validation
  src/components/  # Reusable UI primitives
  src/scene/       # Backend-to-scene mapping and instanced 3D rendering
  src/test/        # API/interaction tests; generated fixture is test-only
docs/
  ARCHITECTURE.md
  DATA_MODEL.md
  DEVELOPMENT_ROADMAP.md
  ML_STRATEGY.md
  PRODUCT_REQUIREMENTS.md
  TEAM_WORKFLOW.md
  UI_UX_SPEC.md
  PART_02_IMPLEMENTATION.md
```

## Getting started

Use Python 3.12 and Node.js 22.12+ (Node 24 is recommended). Internet access is needed to install dependencies. Fonts and geometry are local after installation. Commands below work in PowerShell and do not require activating a script or changing execution policy.

From the repository root, prepare and start the backend:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, from the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:5173**. Keep both terminals running; stop them with Ctrl+C. Vite proxies `/api` to the local backend on port 8000. Use `npm run build` and `npm run preview` for a local production-build demo at **http://127.0.0.1:4173**, with the same backend running. `vite preview` is for local review, not public hosting.

### Verification and contract generation

```powershell
# From backend/
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe export_contract.py

# From frontend/
npm run generate-api
npm run typecheck
npm run lint
npm test
npm run build
```

Regenerate and commit the OpenAPI schema, city JSON Schema, test fixture, and TypeScript declarations whenever the Python contract changes. The generated fixture is used only by tests, never by the application. See [Part 2 implementation notes](docs/PART_02_IMPLEMENTATION.md) for endpoints, coordinates, controls, assumptions, and limitations.

## Data, safety, and scope

- The first demo city and its flood labels are synthetic and repeatable.
- The initial classifier learns a clearly defined synthetic target; it is not evidence of real-world flood forecasting skill.
- Public geospatial data is optional, must be checked for access and terms before use, and must be credited as required by its provider.
- Human approval is required before simulated rescue actions are committed.
- Do not add credentials, raw large datasets, generated checkpoints, or personal data to Git.
- No open-source license is included yet. **Apache-2.0 is the initial recommendation** for a permissive software project with an explicit patent grant; the owner must approve a license before adding it or making the repository public.

## Team and status

Two student developers are planned: one owns the service, simulation, and model pipeline; the other owns the web interface and Digital Twin. Both review integration pull requests and jointly rehearse the demo. See [the roadmap](docs/DEVELOPMENT_ROADMAP.md) and [team workflow](docs/TEAM_WORKFLOW.md).

**Status:** Part 2 full-stack foundation. The initial city and interface are implemented; simulation and intelligence remain future work.
