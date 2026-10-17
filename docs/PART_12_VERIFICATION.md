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

- Corrected fully nested development scenario-group evaluation: raw Brier .0321893 / log loss .1133040; calibrated Brier .0297926 / log loss .1023491. Brier improved .0023966 and log loss delta was −.0109549, satisfying the predetermined gate (.001 Brier improvement and no more than .01 log-loss regression).
- Independence audit: five outer GroupKFold folds hold out 11–12 scenario groups apiece. Each fold's estimator and calibrator fit used only its 45–46 outer-training groups; outer validation groups are disjoint from all three recorded fit-group sets. Inner five-fold grouped OOF scores are generated only within those outer-training groups. The final 15 test groups are absent from every adoption fold and from the production calibrator's 57 development fit groups.
- Production calibration is refit after the gate using five-fold grouped OOF scores over the full development partition. Original random-forest SHA-256 remained `9375c9f2bd919d5124f1320eab04b406c4bf2ae7e63c791fee713122ff843b73`.
- Untouched test raw: Brier .0305264, log loss .1066661, 10-bin ECE .0265378.
- Untouched test Platt: Brier .0279169, log loss .0941896, 10-bin ECE .0050088. F1 at .5 is .966182 (precision .9695, recall .9629); ROC-AUC remains .994494 because Platt is monotone.
- Adoption decision: Platt calibration remains adopted based only on the nested development gate. Final test metrics above are descriptive synthetic holdout results and did not influence adoption.
- Reproducibility metadata: seed 92021, Python 3.12.5, NumPy 2.5.4, scikit-learn 1.9.1. The report's dataset, original model, model metadata, calibrator, and support artifact SHA-256 values are stored and cross-checked in tests. Calibrator SHA-256: `64d50451b051092b0652a774064349d936c30eae93ce9b73f3790e3a29687ec6`; canonical-newline support SHA-256: `f01bcc84be76cc94b2df955ba5c9a90881e9823454c7aaa6da675833dc5f26f3`.
- Test support: 4,540 within observed support, 125 edge-of-support and 735 outside support (13.6%). The status is not an accuracy guarantee.
- Currently dry subset: 3,648 observations across 15 scenarios; 1,319 newly exposed; precision .947707, recall .893101, F1 .919594, 141 false negatives.
- Sensitivity: 63 validation comparisons; mean nonbaseline flip fraction .023663; mean defined Spearman rank correlation .904420; 30 rank pairs undefined due to constant tied scores. Sensitivity generation ran in approximately 3.2 seconds on the development machine.
- Local warmed batch timing for one 360-building generated city: original model 2.74 ms, calibrator 0.079 ms, feature-support checks 9.94 ms. These are machine-specific measurements.

## Test and delivery status

- Backend after Part 12.1: 75 passed, 1 existing Starlette/httpx TestClient deprecation warning. Added nested outer-fold isolation/seed reproducibility coverage and an explicit failed-gate test proving no production calibrator or calibrated test result is emitted.
- Frontend: 11 files / 35 tests passed; ESLint and TypeScript checking passed; production build passed (Vite warns about the existing large 3D chunks).
- OpenAPI export and frontend generated types completed successfully. The generated scenario fixture's unrelated random IDs were restored.
- Part 10 disposable end-to-end acceptance passed all 17 checks, including inference, six-agent trace, rescue proposal/approval, reservations, dispatch, road-closure blocking and reroute, arrival, completion, resource restoration, read-only replay, and A/B isolation/restart persistence.
- Part 10 demo preflight passed all checks with temporary loopback services and a disposable SQLite database. Services were stopped after validation.
- Browser visual walkthrough was completed using an independently reported `http://127.0.0.1:5173/` browser tab. The Command Center and Model Intelligence Lab rendered; the lab displayed measured calibration, held-out errors, support statuses, subgroup table, and simulation sensitivity values. One existing Three.js `THREE.Clock` deprecation warning appeared in browser console; no visual failure was observed.
- GitHub delivery and hosted CI conclusions are recorded after push/PR creation in the final delivery report.
