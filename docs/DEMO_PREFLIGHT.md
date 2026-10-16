# Demo Preflight

Run `scripts\demo-preflight.ps1` from the repository root. The check prints PASS, WARN or FAIL with a short reason and exits nonzero on FAIL. Use `--export <path>` for a redacted JSON report; it contains check names, dependency versions and status text, not environment variables, credentials or user directory names.

Checks cover Python and Node versions, required Python packages, frontend dependencies, model artifact checksum, dataset/evaluation metadata, backend health, generated city, the six-agent registry, model readiness, active-scenario agent/mission/resource endpoints, SQLite tables, frontend accessibility and loopback runtime URLs.

The SQLite probe is read-only. If no local database exists yet, it reports WARN because startup initializes one. The endpoint checks use GET requests only. They do not advance, create, reset or otherwise mutate scenarios. API checks require the backend and frontend to be running first. `RESQ_API_URL` and `RESQ_WEB_URL` can point to alternate loopback ports after the Vite proxy and FastAPI CORS origin are updated to match; remote host values are reported as configuration failure.

Interpretation:

- **PASS**: the individual check succeeded.
- **WARN**: the app may be ready, but a not-yet-created operational database is expected or a noncritical precondition needs review.
- **FAIL**: fix the reported dependency, runtime, artifact, schema or service problem before presenting.

HTTP health alone is not complete readiness. Use the full disposable acceptance runner for scenario mutation, model inference, agents, rescue and mission flows.
