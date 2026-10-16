# Part 7 Verification

## Local automated checks

Executed from the repository's existing local environments:

| Check | Result |
|---|---|
| Backend full pytest suite | **54 passed** |
| Frontend Vitest | **17 passed** across 7 files |
| TypeScript | Passed |
| ESLint | Passed with 0 warnings after the final cleanup |
| OpenAPI + JSON Schema export | Passed via `backend/export_contract.py` |
| TypeScript API generation | Passed via `npm run generate-api` |
| Production build | Passed; Vite emits a 963.19 kB minified `CityScene` chunk warning (257.27 kB gzip) and a 685.05 kB app chunk (204.83 kB gzip) |
| Real local ML / flood / six-agent acceptance script | **PASS**; evidence in [DEMO_ACCEPTANCE_REPORT.md](DEMO_ACCEPTANCE_REPORT.md) |

The first pytest invocation used the Windows shared temp directory and failed during fixture setup with an access-denied error. The suite was rerun using a backend-local `--basetemp=.pytest-tmp-part7` path and completed with 54 passing tests.

## Frontend tests added

- `frontend/src/test/comparison.test.tsx`: verifies same-snapshot builder context, both variants' road choices, and simulation horizon control.
- `frontend/src/test/demo.test.tsx`: verifies initialization and 12-tick flood-stage transitions through the API client boundary, plus failure reporting without stage advancement.

The backend experiment suite covers deterministic reruns, live state/outbox/plan isolation, resource-only physical equality, rainfall-driven divergence, graph route closure, stale/invalid inputs, cancellation, persistence, and experiment API retrieval.

## Browser walkthrough

Verified in the local Codex in-app browser against `http://127.0.0.1:5173/demo` and the local FastAPI service: scenario initialization; flood progression to tick 12 with 59 exposed buildings and 8 exposed roads; local ML output (59 physical exposure vs 70 predicted future-exposed); a completed six-agent trace; four mission proposal; route-relevant closure of `road-ew-1`; real replan where the affected pair became unreachable; explicit commander approval; completed isolated A/B experiment; and navigation to the persisted Decision Explorer trace. The approved-unit reset warning was shown and dismissed without resetting the scenario.

## Performance and limitations

One local severe 12-tick progression took 119 ms. The actual 0-tick resource comparison from a 30-minute snapshot completed in 357.4 ms with 111,294 serialized result bytes in that run. The model timing is sensitive to whether the local artifact is already loaded. The browser build already lazily imports `CityScene`, so pages that do not render the Digital Twin avoid its heavy canvas chunk. The guided demo does not run a second WebGL canvas. The 3D chunk still exceeds Vite's 500 kB advisory; do not split Three.js vendor code further without a measured rendering/startup benefit because the canvas route is the 3D product itself and this would not reduce its total transferred code.

The model outputs and scenario measurements are synthetic. No browser walkthrough proves emergency-response fitness. The backend has no mission completion or automatic resource-release behavior.

## CI and delivery

GitHub Actions run **#10** (`38850236747`) completed successfully after the branch was pushed. Both the `backend` job (dependency install and full pytest suite) and `frontend` job (typecheck, ESLint, Vitest, and production build) passed. The follow-up documentation commit is covered by a subsequent run on the same PR head. No merge is performed.
