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

## Repository map

```text
docs/
  ARCHITECTURE.md
  DATA_MODEL.md
  DEVELOPMENT_ROADMAP.md
  ML_STRATEGY.md
  PRODUCT_REQUIREMENTS.md
  TEAM_WORKFLOW.md
  UI_UX_SPEC.md
```

## Getting started

Implementation begins after the architecture review. The repository currently contains the project foundation and does not yet include a runnable application. The intended local development commands and dependency versions will be documented with the first implementation slice.

## Data, safety, and scope

- The first demo city and its flood labels are synthetic and repeatable.
- The initial classifier learns a clearly defined synthetic target; it is not evidence of real-world flood forecasting skill.
- Public geospatial data is optional, must be checked for access and terms before use, and must be credited as required by its provider.
- Human approval is required before simulated rescue actions are committed.
- Do not add credentials, raw large datasets, generated checkpoints, or personal data to Git.
- No open-source license is included yet. **Apache-2.0 is the initial recommendation** for a permissive software project with an explicit patent grant; the owner must approve a license before adding it or making the repository public.

## Team and status

Two student developers are planned: one owns the service, simulation, and model pipeline; the other owns the web interface and Digital Twin. Both review integration pull requests and jointly rehearse the demo. See [the roadmap](docs/DEVELOPMENT_ROADMAP.md) and [team workflow](docs/TEAM_WORKFLOW.md).

**Status:** Part 1 foundation. Implementation has not started.
