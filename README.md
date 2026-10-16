# RESQ-AI

**Predict. Simulate. Plan. Review. Replan.**

RESQ-AI is an offline-first disaster response command center for a deterministic fictional city. Part 3 adds a stateful flood simulation, locally persisted scenario engine, transparent infrastructure exposure, and an interactive 3D Digital Twin. Part 4 adds a locally trained classifier for synthetic building exposure 30 minutes ahead. It is a decision-support prototype, not an operational warning or dispatch system.

## What the demonstration will show

1. Load the same seed-based city and scenario on every run.
2. Increase rainfall and river stage, then inspect simulated inundation and affected assets.
3. Inspect backend-computed current exposure and event history; replay a selected tick.
4. Compare current exposure with a separately labeled 30-minute synthetic ML estimate in the Model Intelligence Lab.
5. Generate a flood-aware rescue plan, compare exact constrained assignment with a nearest-unit baseline, review ranked destinations, and explicitly approve or reject a proposal.
6. Observe six persisted algorithmic agents replan after measured flood/access changes or a manual road closure, review a replacement in the 3D command center, then make an explicit human decision.
7. Run a reproducible isolated A/B experiment from one saved snapshot, compare actual flood and resource-allocation outcomes, inspect source metrics, and switch the single Digital Twin canvas between variants.
8. Use **Guided Demo** for the ten-stage flood-to-replanning journey, including local ML, event traces, road closure, human decision, and saved baseline-versus-optimized comparison.
9. Approve a proposal to create persistent ready missions, explicitly dispatch a simulated unit, advance the independent operational clock, review a closure-triggered route proposal, confirm arrival/completion, and inspect resource history in Mission Operations and the 3D Digital Twin.

Every displayed metric must come from backend state or a recorded experiment. Simulated data, assumptions, and model results will be labeled as such. No hosted AI inference or external AI API key is part of the design. Once dependencies and any optional data are installed, the application must run locally without network access.

## Planned stack

- **Web:** React, TypeScript, Vite, Tailwind CSS, shadcn/ui, Framer Motion, React Three Fiber, Three.js, Recharts.
- **Service:** Python, FastAPI, Pydantic, SQLite, local REST endpoints with safe polling.
- **Model and algorithms:** scikit-learn, NumPy, pandas, joblib, NetworkX; simple deterministic algorithms first. OR-Tools is optional and must justify its added setup cost.
- **Verification:** pytest, TypeScript type checks and linting, component and integration checks, deterministic simulation scenarios.

The backend owns scenario state, simulation steps, predictions, agent decisions, assignments, and event history. The 3D scene renders a read-only projection of that state and sends user commands back through the API.

## Current implementation — Parts 3–7

The local full-stack foundation renders backend-generated city geometry and inventory. Command Center and Digital Twin Studio include building selection, an API-backed inspector, camera reset/focus/orbit/zoom/pan, map layers, snapshot export, and a building-inventory fallback. The other three routes explain their future scope. Connection status is based on successful local API requests, with retries and a stale-snapshot warning when the service disconnects.

The seeded baseline contains 72 buildings, four districts, ten road corridors, six bridge crossings, one hospital, one shelter, two parks, and five response units. Part 3 adds a deterministic 20 m flood grid, SQLite scenarios/events/checkpoints, replay, and exposure modeling. Part 4 provides offline training/inference and a predicted exposure layer. Part 5 adds an intersection-connected NetworkX route graph, bridge segments, flood-aware ground routes, transparent destination priorities, constrained assignment with a baseline comparison, persistent plan proposals, commander approval/rejection, manual closure overlays, and 3D route display. All simulation and ML data are synthetic and are not validated for real disasters. Boat routing remains unsupported.

Part 6 adds six deterministic local agents, a transaction-backed SQLite event outbox, durable run/decision traces, stale-state rejection, automatic route-aware proposal updates, and a polling AI Decision Explorer. It reuses the Part 5 ML, priority, route and SciPy assignment contracts. Recommendations remain subject to commander approval. Details: `docs/PART_06_IMPLEMENTATION.md`, `docs/AGENT_ARCHITECTURE.md`, `docs/EVENT_ORCHESTRATION.md`, `docs/DECISION_TRACE_CONTRACT.md`, `docs/REPLANNING_POLICY.md`, and `docs/PART_06_VERIFICATION.md`.

Part 7 adds isolated SQLite-backed A/B experiments from one exact scenario snapshot, existing-engine flood variations, resource and manual-road interventions, measured conventional-nearest versus priority-weighted SciPy assignment, saved result charts/JSON export, a one-canvas A/B Digital Twin view, and the guided ten-stage demo. Experiments do not mutate operational scenarios, plans, outboxes, traces or reservations. The demo uses seed 2026, 90 mm/h rain, 1.4 m river stage, 20% drainage and 12 ticks; its acceptance script verifies actual ML inference, six-agent traces, route closure invalidation, replanning, approval and reservation safety. See `docs/PART_07_IMPLEMENTATION.md`, `docs/SCENARIO_COMPARISON.md`, `docs/BASELINE_COMPARISON_METHOD.md`, `docs/HACKATHON_DEMO_GUIDE.md`, `docs/DEMO_ACCEPTANCE_REPORT.md`, and `docs/PART_07_VERIFICATION.md`.

Part 8 adds persistent missions after approval, explicit dispatch, backend-authoritative route progression on a separate operational clock, closure-triggered blocking and reviewed route changes, explicit arrival/completion, durable replay events, and unit return-to-service controls. Browser refresh and service restart do not release resources. A dispatched cancellation or completed mission leaves the unit unavailable until explicitly restored at its recorded position; no return trip is fabricated. Mission metrics and occupant targets are synthetic. See `docs/PART_08_IMPLEMENTATION.md`, `docs/MISSION_LIFECYCLE.md`, `docs/MISSION_CLOCK_MODEL.md`, `docs/RESOURCE_RELEASE_POLICY.md`, `docs/MISSION_EVENT_CONTRACT.md`, `docs/MISSION_DEMO_GUIDE.md`, and `docs/PART_08_VERIFICATION.md`.

Part 5 assumptions and verification are documented in `docs/PART_05_IMPLEMENTATION.md`, `docs/PART_05_VERIFICATION.md`, `docs/ROUTING_MODEL.md`, `docs/RESOURCE_OPTIMIZATION.md`, and `docs/RESCUE_PLAN_CONTRACT.md`.

## Repository map

```text
backend/
  app/             # Configuration, Pydantic schemas, seed service, FastAPI routes
  demo_acceptance.py # Real local-ML flood-to-replanning acceptance run
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
  PART_06_IMPLEMENTATION.md
  PART_07_IMPLEMENTATION.md
  PART_07_VERIFICATION.md
  SCENARIO_COMPARISON.md
  BASELINE_COMPARISON_METHOD.md
  HACKATHON_DEMO_GUIDE.md
  DEMO_ACCEPTANCE_REPORT.md
  PART_06_VERIFICATION.md
  AGENT_ARCHITECTURE.md
  EVENT_ORCHESTRATION.md
  DECISION_TRACE_CONTRACT.md
  REPLANNING_POLICY.md
  AGENT_DEMO_SCENARIO.md
  DATA_MODEL.md
  DEVELOPMENT_ROADMAP.md
  ML_STRATEGY.md
  PRODUCT_REQUIREMENTS.md
  TEAM_WORKFLOW.md
  UI_UX_SPEC.md
  PART_02_IMPLEMENTATION.md
  PART_03_IMPLEMENTATION.md
  PART_03_VERIFICATION.md
  PART_04_IMPLEMENTATION.md
  PART_04_VERIFICATION.md
  ML_MODEL_CARD.md
  ML_EVALUATION.md
  DATASET_PROVENANCE.md
  ML_REPRODUCTION.md
  FLOOD_SIMULATION_METHOD.md
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

Regenerate and commit the OpenAPI schema, JSON Schemas, test fixture, and TypeScript declarations whenever the Python contract changes. The generated city fixture is used only by tests, never by the application. See [Part 3 implementation notes](docs/PART_03_IMPLEMENTATION.md) and [the flood method](docs/FLOOD_SIMULATION_METHOD.md) for current endpoints, coordinates, controls, assumptions, and limitations.

## Data, safety, and scope

- The first demo city and its flood labels are synthetic and repeatable.
- The initial classifier learns a clearly defined synthetic target; it is not evidence of real-world flood forecasting skill.
- Public geospatial data is optional, must be checked for access and terms before use, and must be credited as required by its provider.
- Human approval is required before simulated rescue actions are committed.
- Do not add credentials, raw large datasets, generated checkpoints, or personal data to Git.
- No open-source license is included yet. **Apache-2.0 is the initial recommendation** for a permissive software project with an explicit patent grant; the owner must approve a license before adding it or making the repository public.

## Team and status

Two student developers are planned: one owns the service, simulation, and model pipeline; the other owns the web interface and Digital Twin. Both review integration pull requests and jointly rehearse the demo. See [the roadmap](docs/DEVELOPMENT_ROADMAP.md) and [team workflow](docs/TEAM_WORKFLOW.md).

**Status:** Parts 3–6 implemented on the Part 6 feature branch. Earthquake scenarios, live-data integration, water rescue, and mission execution remain future work.
