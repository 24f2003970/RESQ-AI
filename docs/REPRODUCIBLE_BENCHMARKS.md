# Reproducible benchmarks

All measurements below are tied to a specific local machine, Python/Node versions, scenario seeds and project commit. Re-run the command for a new machine result; do not treat the saved time as a platform guarantee.

## Part 15 scenario evaluation

From `backend/` run:

```powershell
.\.venv\Scripts\python.exe run_part15_evaluation.py
```

Ten distinct groups cover lower/demo forcing, moderate and severe floods, higher river stage, reduced drainage, an important road closure, bridge disruption, limited units, missing-model fallback and a graph with every road closed. Six fixed flood ticks are run per group; each group contributes one final observation. Each case uses its own temporary SQLite store.

Final recorded run on Windows / Python 3.12.5 / NumPy 2.5.4 / scikit-learn 1.9.1: 3,768.693 ms total. Assignment runtime ranged 0.007–0.289 ms and routing 0.844–185.656 ms. An earlier exploratory run took 1,382.568 ms, so timings are treated as environment/load-sensitive, not guaranteed. The optimized objective improved in 8 cases, tied within 0.01 in 2, and was lower in 0. All-road-closed produced 0 assignments and 9 eligible destinations without a supported route. Data: `evidence/part15/scientific_evaluation.{json,csv,md}` relative to this directory. The test for output shape and truthful refusal is `backend/tests/test_part15_evaluation.py`.

## ML and calibration

The original model and reliability report remain saved under `backend/ml_artifacts/`. On the 15-group untouched synthetic test split: raw Brier 0.030526, log loss 0.106666, ECE 0.026538; Platt Brier 0.027917, log loss 0.094190, ECE 0.005009. The decision to adopt calibration came only from nested grouped development folds, with raw Brier/log loss 0.032189/0.113304 and calibrated 0.029793/0.102349. All probability labels are simulator-derived.

The local warmed 360-row batch profile saved in the Part 12 report measured 2.739 ms for model inference, 0.079 ms for calibration and 9.943 ms for support checks. These historical Part 12 machine timings are not Part 15 reruns.

## Robustness

The Part 13.1 reference run evaluated 11 frozen counterfactual conditions in 348.700 ms total (22.515–50.797 ms per condition); completed payload 264,819 bytes. It began from two assignments, and its later extreme-flood horizon invalidated both original routes. A Part 15 rerun evaluated the same 11 conditions in 991.846 ms (58.337–141.033 ms per condition) with a 264,829-byte payload. In that current run, the two initial routes were already infeasible at the recorded starting tick; all 72 destinations were unserved in each condition, including the all-roads-closed case. These are distinct benchmark snapshots and runtimes, not pooled observations. See [Part 13 verification](PART_13_VERIFICATION.md) for the reference forcing and [Part 15 verification](PART_15_VERIFICATION.md) for the current rerun.

## Mission lifecycle

The Part 14 RC1 benchmark measured 100 persisted one-second clock advances for one unit on a 2 km route. Its corresponding earlier machine run measured mean 21.054 ms, p95 28.994 ms, max 31.289 ms. A later Part 14.2 machine run measured mean 4.412 ms, p95 5.077 ms, max 5.960 ms; these were separate environments/run conditions and must not be pooled. See `backend/benchmark_missions.py` and [Part 14 verification](PART_14_VERIFICATION.md).

## Build and package observations

The most recent Part 14.2 build record reports initial JavaScript 638.95 kB minified / 191.07 kB gzip and lazy CityScene 980.87 kB / 262.75 kB gzip. Vite still warns about large JavaScript chunks. Part 15 verification reruns the build and records its actual output before delivery.

## Reproduction and interpretation

- Backend tests: from `backend/`, `.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp-part15`.
- Frontend tests: from `frontend/`, `npm test`.
- Part 10 and 14 acceptance runners are described in [the demo checklist](VISUAL_DEMO_CHECKLIST.md), [Part 10 verification](PART_10_VERIFICATION.md) and [Part 14 verification](PART_14_VERIFICATION.md).
- ML artifacts can be integrity-checked by the existing model service and ML tests. Do not run the training command unless intending to replace the saved model bundle.

Absolute milliseconds vary by CPU, operating system, process warmth, power mode, background work and database state. Synthetic distance, coverage, scores and exposure are not field measurements.
