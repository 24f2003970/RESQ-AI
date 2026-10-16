# Part 10 Implementation

Part 10 adds reliable local demo operations around the existing simulator without changing the flood, model, agent, rescue, mission or experiment contracts.

- `scripts/setup-resq-ai.ps1` creates/reuses an isolated Python 3.12 venv and installs the pinned Python/npm dependencies.
- `scripts/start-resq-ai.ps1` checks dependencies, local model and SQLite availability, starts the loopback API, waits for actual health, launches the development frontend or a production build preview, waits for frontend HTTP response, and stops its service processes when the launcher exits. It reports measured startup readiness times.
- `scripts/demo_preflight.py` checks runtime versions, dependencies, trained artifact checksum, dataset/evaluation metadata, live local endpoints, SQLite schema through a read-only connection and frontend accessibility. It can export a redacted JSON report.
- `backend/demo_acceptance_part10.py` uses disposable SQLite and the production API to exercise flood, ML, six-agent traces, rescue approval, mission lifecycle, restart, route disruption/review, replay, return-to-service and A/B isolation. `--test-commander-actions` is mandatory.
- Documentation records offline boundaries, recovery, reproducible demo settings, test evidence and graphics verification status.

Request logs are structured JSON with UTC timestamp, request ID, method, path, status, applicable scenario/mission ID and elapsed milliseconds. They intentionally omit request bodies and machine paths. Full results and measured commands belong in `docs/PART_10_VERIFICATION.md`.
