# Part 3 Verification Record

Verification performed locally on the Part 3 branch after the implementation changes. The flood model is synthetic; these checks establish software behavior, not real-world predictive accuracy.

## Automated checks

- Backend: `python -m pytest -q --basetemp temp\pytest` — **20 passed**. Coverage includes deterministic terrain/simulation, seed-matched city elevations, volume accounting, bounded drainage/nonnegative depth, building/road/bridge impacts, river-driven land flooding, scenario lifecycle/reset/replay, checkpoint parameter replay, SQLite persistence, stale versions/illegal transitions, parameter validation, API replay, and idempotent creation.
- Frontend: `npm test -- --run` — **7 passed** across 2 test files, including scenario control requests, step, and replay.
- `npm run typecheck` — passed.
- `npm run lint` — passed with no lint findings.
- `npm run build` — passed in under one second in this run. Vite reports `CityScene` at about 962 kB minified (257 kB gzip), above its 500 kB advisory threshold; this is a known optimization item.
- `python -m pip check` — no broken requirements.
- `npm audit --audit-level=moderate` — **0 vulnerabilities reported**.

The backend suite currently emits a dependency deprecation warning from Starlette's `TestClient` integration with `httpx`; it does not fail tests. A dependency security audit and OS-level network-disconnection test were not performed in this verification run. The app makes no hosted inference/API calls; offline runtime still requires installed local dependencies and a running local service.

## Manual browser verification

In the Codex in-app browser at `http://127.0.0.1:5173`, the Command Center loaded with a connected local service and rendered the seeded isometric city, facility markers, inventory fallback control, exposure legend, and inspector. Scenario Lab loaded the three deterministic presets and explicit model-limit labels. Selecting heavy rainfall created a scenario with 90 mm/h, 0.25 m river stage, and 45% drainage; two manual 5-minute steps advanced the backend state from tick 0 to tick 2 / 10 simulated minutes. The UI showed 0.01 m maximum depth, no affected buildings, and a near-zero volume balance residual (`3.64e-12 m³`). Seeking replay to tick 0 showed a read-only reconstructed state and disabled mutating controls. Reset returned to tick 0, paused, with zero mass-balance error. The 3D scene remained rendered on the Command Center during the walkthrough. Restarting FastAPI then returned the same SQLite scenario ID, tick 0, state version 4, and 90 mm/h preset, confirming local persistence across service restart.

Screenshots were visually inspected in the browser session but were not saved as repository image files. This avoids committing machine-specific captures; the PR description records the browser observations. No OS-level network disconnection was performed. The app has no external inference/API runtime dependency, but a local backend and previously installed frontend/backend dependencies are required.
