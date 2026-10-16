# Local Demo Quickstart

## Requirements

- Windows PowerShell 5.1 or newer.
- Python 3.12 available through the Python Launcher (`py -3.12`).
- Node.js 22.12 or newer and npm.
- The repository's locally trained model artifact under `backend/ml_artifacts/`.

Internet is needed for first-time package installation. Runtime app assets, fonts, maps, model inference and API calls are local. This project is a fictional prototype and is not approved for real emergency operations.

## First-time setup

From the repository root:

```powershell
.\scripts\setup-resq-ai.ps1
```

This creates `backend/.venv` if missing, installs the pinned backend requirements there, and runs `npm ci` under `frontend`. It does not change global Python packages. To only verify/create environments without installing packages, use `-SkipInstall`.

## Everyday development startup

```powershell
.\scripts\start-resq-ai.ps1
```

Open http://127.0.0.1:5173. FastAPI is at http://127.0.0.1:8000. The launcher verifies its health before starting the frontend. Ctrl+C stops both child services. If port 8000 or 5173 is occupied, close the existing local service and rerun. The launcher never removes or resets SQLite data.

## Production-built local demo

```powershell
.\scripts\start-resq-ai.ps1 -Mode production
```

This runs the production build first, then serves it locally at http://127.0.0.1:4173 while using the same local backend. `vite preview` is a local demonstration server, not a public deployment configuration.

## Preflight and diagnostics

With the services running:

```powershell
.\scripts\demo-preflight.ps1
.\scripts\demo-preflight.ps1 --export .\artifacts\demo-preflight.json
```

The preflight endpoint probes are GET-only. Its SQLite check opens an existing database in read-only mode. See [Demo Preflight](DEMO_PREFLIGHT.md).

## Acceptance run

```powershell
.\backend\.venv\Scripts\python.exe .\backend\demo_acceptance_part10.py --test-commander-actions
```

It uses a disposable SQLite database, real FastAPI routes and explicit simulated commander approval/dispatch. Reports are saved under `artifacts/part10-acceptance/`. It does not point at the normal operational database. See [End-to-End Acceptance](END_TO_END_ACCEPTANCE.md).

## Low-graphics contingency

If WebGL is unavailable or slow, switch on the app's low-graphics setting and use the scenario, model, agent, rescue and mission panels as the primary demonstration. Follow the browser checklist when a browser session is available; build/test checks do not verify rendered 3D output.

## Repeatable Guided Demo sequence

Open **Guided Demo** and select **Initialize demo scenario**. It creates a separate scenario with seed `2026` and a mild initial preset, leaving other scenarios untouched. Confirm the local model is ready before presenting its prediction stage. The walkthrough applies 90 mm/h rainfall, a 1.4 m river stage and 20% drainage, then advances 12 five-minute ticks. Read actual physical exposure counts and the persisted six-agent trace. See [Hackathon Demo Guide](HACKATHON_DEMO_GUIDE.md) for the full stage-by-stage script.

Next, review the computed rescue proposal and explicitly approve it. Dispatch a ready mission in Mission Operations, advance the separate mission clock, and close a road listed in that unit's current route. The app should show the blocked mission. Request a route revision and approve the proposed route explicitly when reachable; if the service returns an unreachable result, keep the unit blocked. Continue the approved route to arrival, explicitly complete it, then use return-to-service to release the unit. Inspect the mission replay and AI decision trace, then run the documented A/B comparison stage.

To repeat, use the Guided Demo's **Reset and run again** action. It resets only its separate demo scenario, starts a new epoch, and keeps earlier trace/mission history. The Part 10 acceptance command is an alternate reset-safe demonstration: every run creates a temporary database and removes it with the worker process. Never delete the local SQLite file to prepare a demo. Mission details are in [Mission Demo Guide](MISSION_DEMO_GUIDE.md).
