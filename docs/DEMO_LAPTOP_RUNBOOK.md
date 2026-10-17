# Windows demo-laptop runbook

## Prerequisites

- Windows 10/11 with Python 3.12 and Node.js 22.12 or newer.
- Local Python environment at `backend/.venv`, npm packages at `frontend/node_modules`, and the checked-in local model artifact plus metadata.
- No cloud credentials or external AI API key. After dependencies are installed, runtime requests use loopback only; no claim of OS-level network isolation is made.

## Start, diagnose and stop

From the repository root, run `scripts\start-resq-ai.ps1`. It verifies runtimes/dependencies/model presence, checks an existing SQLite file read-only, tests ports 8000 and 5173/4173, waits for backend health before starting Vite, prints the actual frontend URL, and owns both child processes. Run `scripts\demo-preflight.ps1` for the read-only diagnostic report. Press Ctrl+C in the launcher terminal to stop both children. Preserve the database if startup or shutdown fails; inspect the reported PID/port before retrying.

Default data path is relative to the repository: `backend/data/resq.sqlite3`. Set `$env:RESQ_DB_PATH` to a chosen local SQLite path before launching to isolate demo data. Do not delete user data to repair startup. `--production` builds and serves local production assets on loopback port 4173; it requires the same Python model and local database.

## Recovery behavior

Mission/plan/event rows and resource status persist in SQLite across browser refresh and backend restart. A recovered in-flight mission remains at its persisted position and requires the next explicit clock advance. Pending agent events are recovered by the app lifespan. Ready cancellation releases its reservation; an arrived/completed/dispatched-cancelled unit requires explicit return-to-service. Reset begins a new resource epoch and retains historical records. If the optional model is unavailable, model endpoints degrade; the physical simulator and non-ML route/mission APIs remain separate. The RC1 disposable runner exercises the positive and all-road-closed cases without writing to the user's database.

## RC1 workstation observation

On the Windows 11 workstation used for verification (Intel Core i5-13500HX, 14 cores / 20 threads, Intel UHD and NVIDIA RTX 4050), the Part 10 launcher confirmed loopback-only API/UI readiness against a disposable RESQ_DB_PATH; observed backend readiness was about 5.4 s and Vite readiness about 1.2 s. The launcher owns both child processes, honors Ctrl+C shutdown, and did not delete or migrate the repository's user database. Exact browser-side shutdown duration was not separately timed. The manifest lists the actual Python 3.12.5 and Node 24.12.0 runtime versions.
