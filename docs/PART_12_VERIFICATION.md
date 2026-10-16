# Part 12 — Verification Record

This record is updated from commands run on the Part 12 branch. All model metrics are synthetic-simulator results.

## Baseline and reproducibility

- `origin/main` was verified at Part 11 merge `9cb8e6572d65b1ed012c5768c7f10d00920da22`.
- Baseline before Part 12 edits: backend 67 passed; frontend 33 passed.
- Regenerated dataset: 72 scenario groups, 25,920 observations, 17,298 positives and 8,622 negatives. CSV SHA-256: `c560bdb345ad083f3f8e1d9d8a2d4928d2705bd7787f4e9640567a439040387d`.
- Original model artifact SHA-256 remained `9375c9f2bd919d5124f1320eab04b406c4bf2ae7e63c791fee713122ff843b73`.
- Test split remains 15 whole scenario groups / 5,400 observations. Confusion: TN 2,264, FP 65, FN 141, TP 2,930. Precision .978297, recall .954087, F1 .966040, balanced accuracy .963089, ROC-AUC .994494, AP .995985.
- Group leakage is absent: 42 train, 15 validation and 15 test scenario IDs. Features use current observations and static generated building fields; target uses the later six flood ticks.

## Calibration and support

- Nested grouped development OOF Brier: raw .0321893, Platt .0298491. Adoption threshold was at least .001 Brier improvement and no more than .01 log-loss regression; development evaluation passed.
- Untouched test raw: Brier .0305264, log loss .1066661, 10-bin ECE .0265378.
- Untouched test Platt: Brier .0279169, log loss .0941896, 10-bin ECE .0050088. F1 at .5 is .966182 (precision .9695, recall .9629); ROC-AUC remains .994494 because Platt is monotone.
- Test support: 4,540 within observed support, 125 edge-of-support and 735 outside support (13.6%). The status is not an accuracy guarantee.
- Currently dry subset: 3,648 observations across 15 scenarios; 1,319 newly exposed; precision .947707, recall .893101, F1 .919594, 141 false negatives.
- Sensitivity: 63 validation comparisons; mean nonbaseline flip fraction .023663; mean defined Spearman rank correlation .904420; 30 rank pairs undefined due to constant tied scores. Sensitivity generation ran in approximately 3.2 seconds on the development machine.
- Local warmed batch timing for one generated city: original model 10.49 ms, calibrator 0.255 ms, feature-support checks 32.77 ms. These are machine-specific measurements.

## Test and delivery status

- Backend: 73 passed, 1 existing Starlette/httpx TestClient deprecation warning.
- Frontend: 11 files / 35 tests passed; ESLint and TypeScript checking passed; production build passed (Vite warns about the existing large 3D chunks).
- OpenAPI export and frontend generated types completed successfully. The generated scenario fixture's unrelated random IDs were restored.
- Part 10 disposable end-to-end acceptance passed all 17 checks, including inference, six-agent trace, rescue proposal/approval, reservations, dispatch, road-closure blocking and reroute, arrival, completion, resource restoration, read-only replay, and A/B isolation/restart persistence.
- Part 10 demo preflight passed all checks with temporary loopback services and a disposable SQLite database. Services were stopped after validation.
- Browser visual walkthrough was completed using an independently reported `http://127.0.0.1:5173/` browser tab. The Command Center and Model Intelligence Lab rendered; the lab displayed measured calibration, held-out errors, support statuses, subgroup table, and simulation sensitivity values. One existing Three.js `THREE.Clock` deprecation warning appeared in browser console; no visual failure was observed.
- GitHub delivery and hosted CI conclusions are recorded after push/PR creation in the final delivery report.
