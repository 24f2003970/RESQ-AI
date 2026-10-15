# Part 6 verification

## Reproducible pipeline measurement

Run `backend/benchmark_agents.py` with the installed local model artifacts. It creates an isolated SQLite database, uses seed 2026 / extreme preset, sets rainfall to 300 mm/h, river stage to 5 m, drainage effectiveness to 0, advances 120 deterministic steps, then processes the persisted simulation event through all six agents.

Measured run (Windows, Python 3.12, 2026-10-15; one cold local-model inference):

| Measurement | Time |
|---|---:|
| Event outbox insertion | 0.103 ms |
| Local ML inference | 153.187 ms |
| NetworkX routing agent | 39.212 ms |
| SciPy assignment solver call | 0.679 ms |
| Full resource-allocation agent | 2.750 ms |
| Proposal persistence | 2.883 ms |
| Event-to-trace pipeline | 408.641 ms |
| Measured caller wall time | 426.995 ms |

The run completed all six agents with model status `ready`, created one commander-review proposal, and found 72 affected buildings and 10 exposed roads. Times are one measured run and depend on machine/model cache state; they are not estimates or performance guarantees. The local estimator uses synthetic labels and is not calibrated for real floods.

## Backend regression coverage added

`backend/tests/test_agents.py` covers: ordered six-agent persistence and duplicate idempotency; measured timing evidence; explicit model-unavailable degraded fallback without invented predictions; stale infrastructure rejection; two concurrent processor instances; restart-style recovery; replay without operational outbox effects; epoch isolation and reservations; approved-unit exclusion on the next proposal; a real route-edge change after closing `road-ew-1`; superseding the previous proposal; and a closure racing proposal persistence. Existing rescue contract tests also now assert that an already reserved unit is rejected during proposal save, before approval.

## Frontend regression coverage added

`frontend/src/test/agents.test.tsx` covers persisted status/trace display, event timeline and route evidence, historical-epoch warning, backend-disconnected state, and assessment queueing/navigation. API responses are validated against generated JSON schemas; TypeScript types are generated from current OpenAPI.

## Full checks

Final local verification (2026-10-15):

| Check | Result |
|---|---|
| Backend: `python -m pytest -q --basetemp=.pytest-tmp-part6-run` | 47 passed; one upstream Starlette/httpx deprecation warning; 11.30 s |
| Frontend: `npm test -- --run` | 14 passed across 5 files; 3.87 s |
| Frontend lint: `npm run lint` | passed |
| Frontend TypeScript: `npm run typecheck` | passed |
| Frontend production build: `npm run build` | passed; Vite reports the existing large 3D chunk warning (963.19 kB) |
| Generated API contracts | backend export and `npm run generate-api` passed |
| `git diff --check` | passed; Git printed only line-ending normalization warnings |

The pytest base directory is explicitly inside the backend workspace because this Windows environment denies access to the default user Temp pytest directory.

## Browser review

The local backend and frontend were opened in Chrome at `/decisions`; the AI Decision Explorer rendered its scenario context, all six agent cards, empty-state inspector and coordination flow. Automated frontend tests cover live activity/trace display and assessment navigation. This browser check did not simulate a live event in the browser.
