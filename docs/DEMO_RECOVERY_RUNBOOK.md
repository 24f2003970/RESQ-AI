# Demo Recovery Runbook

## Before presenting

1. Start with `scripts\start-resq-ai.ps1` and run `scripts\demo-preflight.ps1`.
2. Confirm model readiness, six local agent definitions, mission endpoints and the frontend check all pass.
3. Keep the backend and frontend terminal visible so startup errors are easy to find. Request logs include a generated request ID, method, local path, response status and duration; server exceptions include that request ID.
4. Use a disposable demo scenario created in the UI. Do not reset or delete the default database as a troubleshooting step.

## If startup fails

- Missing Python/Node: install Python 3.12 and Node.js 22.12+, then rerun `scripts\setup-resq-ai.ps1`.
- Missing packages: rerun setup; dependencies remain scoped to `.venv` and `node_modules`.
- Missing/incompatible local model: confirm `backend/ml_artifacts/flood_exposure_v1.joblib`, metadata and pinned scikit-learn requirements are present. Do not substitute a fabricated model result.
- Port busy: close the prior local RESQ-AI process. The launcher detects ports 8000, 5173 or 4173 and stops its own child processes on startup failure or Ctrl+C.
- SQLite error: preserve the database file and diagnostics. Run `scripts\demo-preflight.ps1 --export .\artifacts\demo-preflight.json`; the report omits secrets and home-directory paths.

## If the UI loses the service

Wait for the local API to recover, then refresh the app and read current scenario/mission state before retrying a mutation. Do not blindly repeat a non-idempotent action. The API's idempotency-key commands are safe to retry only with the exact same key and request. Human plan and route approvals remain explicit.

## If the 3D view fails

Use low-graphics mode and the scenario/agent/mission panels as a contingency. Never describe a simulated proposal as a completed rescue. The mission remains at its saved state across browser refresh and backend restart. Completion and resource return-to-service are explicit actions. See the [manual visual walkthrough](PART_10_VERIFICATION.md).

The product is a fictional local decision-support prototype, not an emergency service.
