# Part 15 verification

Verification is reported as observed on the local Windows development environment. Machine-specific durations are not portable performance guarantees. The feature branch started from the verified Part 14 merge `79a77c991431d1bcc1cc1aba8b1eebc2e10b6552`.

## Baseline

- Backend: 89 passed; one existing Starlette/httpx deprecation warning. Pytest used repository-local `--basetemp=.pytest-tmp-part15` after the default Windows temp location returned a permissions error.
- Frontend: 52 passed across 14 files.
- Baseline branch worktree was clean; existing untracked `backend/part9-baseline/` and `pytest-part7-baseline/` were preserved.

## Part 15 evaluation

Command: `backend/.venv/Scripts/python.exe backend/run_part15_evaluation.py`

Final recorded runtime: 3,768.693 ms for ten groups. Priority-weighted objective improved in 8 groups, tied within 0.01 in 2, and was lower in 0. No assignments were produced in two groups; all-road-closed produced zero assignments and nine unreachable eligible destinations. Route calculation ranged 0.844–185.656 ms per group; assignment ranged 0.007–0.289 ms. An earlier exploratory run took 1,382.568 ms; per-run variation is retained in the record rather than presented as a guaranteed duration. These are local measurements.

The comparison's objective is the planner's priority-weighted assignment objective, not a count of real people rescued. Full per-case metrics and assumptions are in `evidence/part15/scientific_evaluation.csv` and `.md`. The runner regression test checks ten unique scenario groups, fallback status, solver result, all-road-closed behavior, artifact hashes, CSV outputs, and a disposable database.

## Existing-project baseline acceptance evidence

The immediately preceding merged Part 14 record reports:

- Part 10 preflight: 24/24; disposable Part 10 acceptance: 17/17.
- Part 14 Demo A/B acceptance: 14/14.
- Part 13 historical robustness benchmark: 11 conditions, 370.001 ms total in that recorded run, 21.906–47.739 ms per condition.
- Mission persistence benchmark: 100 advances; mean 4.412 ms, p95 5.077 ms, max 5.960 ms in that recorded run.
- Browser verification included approval, dispatch, progress, closure/blocking, no-safe-route response, reopening, reviewed route revision, arrival, explicit completion and resource restoration. The closed-road demo had no supported detour while closed.

These historical values are attributed to the Part 14 record and are not represented as rerun Part 15 timings. Part 15 does not modify operational code.

Part 15 reran the Part 13 robustness benchmark: 11 conditions, 991.846 ms total, 58.337–141.033 ms per condition, 264,829-byte payload. At this later synthetic snapshot, the two original assignments were already infeasible and all 72 destinations were unserved in each of the 11 variants; all-road closures also yielded zero assignments. This is a different state and run from the historical 348.700 ms Part 13 report, so the values are not pooled.

## Full final verification

The following must be run after final documentation and evaluation changes; results are recorded in the delivery report and updated here before commit:

```powershell
# Repository root
.\backend\.venv\Scripts\python.exe -m pytest --basetemp=.pytest-tmp-part15
.\backend\.venv\Scripts\python.exe .\backend\run_part15_evaluation.py
.\backend\.venv\Scripts\python.exe .\backend\demo_acceptance_part10.py --test-commander-actions
.\backend\.venv\Scripts\python.exe .\backend\demo_acceptance_rc1.py
.\backend\.venv\Scripts\python.exe .\backend\benchmark_robustness.py
.\scripts\demo-preflight.ps1

# frontend/
npm test -- --reporter=dot
npm run lint
npm run typecheck
npm run generate-api
npm run build
```

The backend contract export was run from `backend/` with `.venv/Scripts/python.exe export_contract.py`.

| Check | Final result |
|---|---|
| Backend Pytest | **90 passed**, one existing Starlette/httpx deprecation warning, 76.87 s |
| Part 15 focused evaluation regression | **1 passed**, 21.40 s |
| Frontend Vitest | **52 passed**, 14 files |
| ESLint | Passed |
| TypeScript | Passed |
| OpenAPI contract export | Passed |
| Frontend API type generation | Passed |
| Production build | Passed; existing Vite large-chunk warning. Initial JS 638.95 kB min / 191.07 kB gzip; CityScene 980.87 kB / 262.75 kB gzip |
| Part 10 preflight | **24/24 passed** |
| Part 10 disposable acceptance | **17/17 passed** in 29,534 ms |
| Part 14 RC1 Demo A/B acceptance | **14/14 passed** in 32,717 ms |
| Part 13 robustness benchmark, Part 15 rerun | **11 conditions**, 991.846 ms total, 58.337–141.033 ms per condition, 264,829-byte payload |
| Part 15 ten-group evaluation | **10 groups**; final run 3,768.693 ms; 8 improved, 2 tied, 0 lower; 2 zero-assignment cases |
| Reliability plot regeneration | Passed from saved Part 12 reliability evidence |

ML integrity checks compared the saved reliability report with local artifacts. Random forest SHA-256 `9375c9f2bd919d5124f1320eab04b406c4bf2ae7e63c791fee713122ff843b73`, calibrator `64d50451b051092b0652a774064349d936c30eae93ce9b73f3790e3a29687ec6`, support file `f01bcc84be76cc94b2df955ba5c9a90881e9823454c7aaa6da675833dc5f26f3`, normalized metadata `7542b7d10be467ef560ec76bbe105ffc8001c063dfff177375cbef42cb0bf2d4`, and training CSV `c560bdb345ad083f3f8e1d9d8a2d4928d2705bd7787f4e9640567a439040387d` all match the saved report. No model retraining occurred.

The local URL-verified browser captures are documented in `VISUAL_EVIDENCE_GALLERY.md`. Exact target desktop CSS viewports, reduced-motion behavior, and WebGL context-loss recovery remain pending; see `FINAL_VISUAL_QA.md`. Hosted backend/frontend workflow conclusions will be recorded after GitHub Actions completes.
