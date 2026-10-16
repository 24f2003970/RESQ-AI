# Part 10 Verification

## Reproduction commands

```powershell
# From repository root
.\scripts\setup-resq-ai.ps1
.\scripts\start-resq-ai.ps1
.\scripts\demo-preflight.ps1
.\backend\.venv\Scripts\python.exe .\backend\demo_acceptance_part10.py --test-commander-actions

# From backend/
.\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest-tmp-part10

# From frontend/
npm test -- --reporter=dot
npm run lint
npm run typecheck
npm run generate-api
npm run build
```

## Verification record

Environment: Windows 11, Python 3.12.5 in `backend/.venv`, Node 24.12.0, npm 11.6.2. The installed local model artifact checksum matches its metadata.

Branch `feature/part-10-demo-reliability` was created from `origin/main` at verified Part 9 merge `75f8e6e03f840bfcba2a1619d1f068611afe3ae9`.

- Backend: **67 passed** (18.25 s), including three Part 10 tool tests. One existing `StarletteDeprecationWarning` reports `httpx` use by `starlette.testclient` is deprecated; no test failed.
- Frontend: **26 passed** in 10 files (6.98 s).
- ESLint: passed.
- TypeScript: `tsc --noEmit` passed.
- API contract generation: `backend/.venv/Scripts/python.exe export_contract.py` and `npm run generate-api` passed; the generated TypeScript passed `npm run typecheck`. Export regenerated the fixture's random event IDs; that incidental fixture-only change was restored. No generated contract file remains modified.
- Production build: passed. Vite reports the existing large lazy scene chunk warning. The warning threshold was not changed.
- Dependency check: `pip check` reported no broken requirements.
- Setup validation: `scripts/setup-resq-ai.ps1 -SkipInstall` passed against the installed isolated environment.
- Development launcher: backend health readiness **3,128.7 ms**; frontend HTTP readiness **554.9 ms** in one run. Production-preview mode: backend health readiness **2,601 ms**, frontend HTTP readiness **532.8 ms**; production bundle served successfully at port 4173. Ctrl+C stopped both services without a batch confirmation prompt; ports 8000, 5173 and 4173 were confirmed stopped afterward.
- Live preflight: **24/24 checks passed**, **561.5 ms** for one run, including Vite proxy/CORS consistency. Its JSON export is under ignored `artifacts/`.
- Disposable end-to-end acceptance: **PASS**, one run in **8,357.1 ms**. Scenario ID: `scenario-f012d1103272`; flood event `2a029ff5ed014a789a80913a6e879245`; proposal `113e37c5-1417-4e53-adc4-098707c6e29b`; missions `mission-35c0a30599145674ac48`, `mission-361fa055827d50309b8d`, `mission-36f21faa25ec538d9628`, `mission-5e18cdc435465a85b268`; A/B experiment `24f2a37792244048980acae8ae127b63`.

The acceptance run verified six-agent completion, a 12-tick flood with 59 affected buildings and 8 exposed roads, 72 local model predictions, four computed mission assignments, approved-plan/reservation persistence, pending-event recovery after restart, stale-version rejection, idempotent dispatch retry, closure-triggered blockage, an infeasible route response followed by a fresh commander-approved route after reopening, arrival after 52 simulated seconds, explicit completion, return-to-service, read-only replay, and isolated A/B results after restart. The successful run used a temporary database and removed it when its worker process exited. JSON and Markdown evidence are in `artifacts/part10-acceptance/` and are ignored by Git.

### Single-run timing evidence

These are local wall-clock observations. All except mission clock updates have one sample. They are not statistically robust performance claims.

| Operation | Observed time | Samples / context |
| --- | ---: | --- |
| Backend health request | 5.7 ms | 1 |
| Local model metadata and inference for 72 buildings | 37.8 ms | 1 |
| Flood simulation | 525.7 ms | 12 deterministic ticks |
| Six-agent trace retrieval and verification | 34.7 ms | 1 six-agent event |
| Rescue routing | 46.1 ms | 1 generated plan |
| Assignment optimization | 0.148 ms | 1 generated plan |
| Full rescue proposal request | 78.3 ms | Includes routing, assignment and persistence |
| SQLite-backed scenario read | 32.5 ms | 1 GET after restart |
| Scenario creation API | 350.7 ms | 1; includes agent event work, not isolated SQLite latency |
| Approval and mission persistence | 322.2 ms | 1; includes synchronous event handling |
| Mission clock update | 160.9 ms median; 299.7 ms p95 | 2 samples only |
| Full mission arrival progression | 378.9 ms | 1; 52 simulated seconds across 2 clock updates |
| A/B experiment | 425.6 ms | 2 variants × 2 ticks |
| Whole acceptance run | 8,357.1 ms | 1 |
| Live preflight | 561.5 ms | 24 read-only checks, 1 run |

The runner reports sample count, median and a nearest-rank p95. A one-sample p95 equals that sample. Scenario creation and approval timings include application/agent work and must not be described as isolated database latency.

## Browser and CI

Visual browser inspection was not performed. The previous computer-use helper could not establish the active URL, and no independently verified browser session was available. Browser layout, WebGL rendering, GPU metrics and frame rate remain **PENDING**. Use the manual checklist in `GRAPHICS_PERFORMANCE_PART_10.md`.

Hosted GitHub Actions results will be added after PR #10 opens and the backend and frontend jobs finish.

## Known boundaries

- Readiness and acceptance require Python 3.12, Node.js 22.12+ and the local trained model artifact.
- First-time setup uses package registries; app runtime uses loopback services.
- Performance measurements are one run or two samples, not statistically robust distributions.
- Browser rendering/FPS and host-level packet capture remain unverified.
- RESQ-AI is a synthetic local decision-support prototype, not approved for real emergency operations.
