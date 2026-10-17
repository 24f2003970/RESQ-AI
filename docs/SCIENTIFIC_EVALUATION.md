# RESQ-AI scientific evaluation

## Scope

RESQ-AI is an offline, synthetic disaster decision-support prototype. The evaluation measures reproducibility and behavior under the implemented fictional city generator, flood simulator, model artifacts, route graph, and assignment objective. It does not estimate field safety, lives saved, or outcomes in real communities.

## Evaluation questions

| Area | Question | Evidence and method |
|---|---|---|
| Flood simulation | Does a fixed seed and forcing reproduce the same simulated exposure? | Existing deterministic scenario engine and regression tests; fixed five-minute ticks and saved checkpoints. |
| ML prediction | How well does the local classifier label future simulated exposure on unseen generated scenario groups? | 72 generated scenario groups, grouped split, 15 untouched test groups, target six ticks ahead. Metrics in `backend/ml_artifacts/evaluation.json`. |
| Calibration | Does calibration improve held-out development-group probability scores under a nested, group-isolated adoption check? | Five outer GroupKFold splits; each outer split independently trains inner grouped OOF scores and a Platt model. Metrics and group audit in `backend/ml_artifacts/reliability_evaluation.json`. |
| Routing | Are returned routes connected through allowed modeled road geometry? | NetworkX graph segments honor flood depths, unit limits, bridge status, manual closures and endpoint access rules; tests in `backend/tests/test_rescue.py` and mission regressions. |
| Assignment | Does SciPy's maximum-weight assignment improve the declared objective over a transparent feasible greedy baseline under identical inputs? | Ten-group Part 15 runner. Both methods receive the same route map, priorities, units, closures and depth constraints. |
| Agents | Are six ordered local algorithmic agents event-triggered, traceable, durable and subordinate to human approval? | Part 10 disposable acceptance and agent tests. No language-model agent is implied. |
| Mission lifecycle | Are reservations, dispatch, progress, blocked movement, route review, arrival, completion, replay and resource restoration explicit and persistent? | Part 14 Demo A/B disposable acceptance and browser evidence. |
| Robustness | Do frozen hypothetical studies disclose unsupported original plans and avoid changing operational state? | Part 13 benchmark and isolated study tests. |
| Runtime and usability | Do local builds, acceptance runners and supported UI paths complete on the measured laptop? | Machine-specific Part 15 evaluation, build outputs, acceptance runners and the viewport matrix in `FINAL_VISUAL_QA.md`. |

## Reproducible rescue planning study

Run from `backend/`:

```powershell
.\.venv\Scripts\python.exe run_part15_evaluation.py
```

The runner uses ten distinct seeds (`151500`–`151509`) and one terminal scenario state after six deterministic five-minute flood steps. The six ticks within a group are correlated progression and count as one group, not six independent disaster samples. Each case receives a fresh temporary SQLite store, removed after that case; no live operational database is written. The generated JSON, CSV and Markdown summary are checked in under `docs/evidence/part15/`.

| Case | Flood depth (m) | Physical buildings exposed | Greedy baseline | Optimized | Priority-weighted coverage, baseline → optimized | Objective delta | Unreachable destinations |
|---|---:|---:|---:|---:|---:|---:|---:|
| Demo-mild forcing | 0.1916 | 9 | 4 | 4 | 13.76 → 21.32 | +7.62 | 0 |
| Moderate flooding | 0.0599 | 0 | 4 | 4 | 4.80 → 13.45 | +8.65 | 0 |
| Severe flooding | 0.6991 | 70 | 4 | 4 | 12.28 → 37.43 | +25.42 | 41 |
| Increased river stage | 0.4633 | 18 | 2 | 2 | 1.78 → 4.75 | +3.08 | 10 |
| Reduced drainage | 0.0343 | 0 | 0 | 0 | 0.00 → 0.00 | 0.00 | 0 |
| Important road closure | 0.1462 | 10 | 4 | 4 | 8.57 → 26.93 | +18.60 | 0 |
| Bridge disruption | 0.1527 | 7 | 4 | 4 | 7.77 → 19.08 | +11.25 | 0 |
| Limited resources | 0.0340 | 0 | 2 | 2 | 1.43 → 5.24 | +3.78 | 0 |
| Model-unavailable fallback | 0.1995 | 9 | 4 | 4 | 10.92 → 20.03 | +8.74 | 0 |
| All roads closed | 0.1772 | 5 | 0 | 0 | 0.00 → 0.00 | 0.00 | 9 |

The SciPy solver maximized `Σ(priority_score × capacity-covered occupant fraction − 0.15 × synthetic route minutes)`, with at most one destination per unit and at most one unit per destination. The conventional baseline walks the same priority ordering and assigns the nearest feasible remaining unit. It is transparent and feasibility-aware, but it is not globally optimal for that objective. Objective values and travel times are synthetic score units and synthetic graph speeds.

Across these ten fixed cases, optimization improved the declared objective in eight groups, tied within 0.01 in two groups, and was lower in none. This is a descriptive result over this chosen set, not an estimated improvement rate. The severe-flood and all-roads-closed groups retained 41 and 9 unreachable destinations respectively. Every corridor closed produced **zero** ground assignments, the correct supported outcome.

The final recorded runner time was **3,768.693 ms** on the Windows development environment. Per-group assignment took 0.007–0.289 ms; routing took 0.844–185.656 ms. An earlier exploratory run took 1,382.568 ms, so durations vary and are not performance guarantees. Full outputs and environment are in `docs/evidence/part15/scientific_evaluation.json`; compact values are in the adjacent CSV.

## ML evidence and limits

The existing dataset contains 25,920 building observations from **72 scenario groups**, split into 42 train, 15 validation and 15 untouched synthetic test groups. Each building row predicts whether modeled exposure occurs six five-minute ticks (30 minutes) later. Several observations within one scenario share the same simulated history. Group splitting avoids counting correlated rows from one generated disaster in both fit and evaluation folds.

The original random forest remains unchanged (SHA-256 `9375c9f2bd919d5124f1320eab04b406c4bf2ae7e63c791fee713122ff843b73`). The development adoption gate used five outer grouped folds with inner grouped OOF score generation for each outer-training partition. It adopted Platt calibration because nested development Brier improved by 0.002397 and log loss improved by 0.010955. Production Platt fitting then used grouped OOF scores from all 57 development groups. The final 15 groups were not used to select the method or gate.

| Split / scores | Brier (lower better) | Log loss (lower better) | 10-bin ECE (lower better) | Scope |
|---|---:|---:|---:|---|
| Nested development raw | 0.032189 | 0.113304 | 0.028141 | Adoption evidence, outer folds |
| Nested development Platt | 0.029793 | 0.102349 | 0.004885 | Adoption evidence, outer folds |
| Untouched test raw | 0.030526 | 0.106666 | 0.026538 | Descriptive final synthetic holdout |
| Untouched test Platt | 0.027917 | 0.094190 | 0.005009 | Descriptive final synthetic holdout |

On the untouched test labels at threshold 0.5, raw precision was 0.9783, recall 0.9541, F1 0.9660 and balanced accuracy 0.9631; confusion counts were TN 2,264, FP 65, FN 141, TP 2,930. Platt is a monotone mapping, so ROC AUC did not change (0.994494). Final held-out results are synthetic and were not used for the adoption decision. The grouped nested development and final test reliability curves are plotted in [the evidence gallery](evidence/part15/calibration_reliability.svg).

The test partition has 735/5,400 rows (13.6%) outside marginal training support and 125 edge-of-support. The currently dry subgroup includes newly exposed buildings and false negatives; subgroup and failure details are saved in `backend/ml_artifacts/reliability_evaluation.json`. Support checks flag observed-feature range issues but cannot detect all feature combinations. High synthetic metrics do not establish calibration or predictive accuracy on real flood outcomes.

## Robustness and failure evidence

The current Part 13 study is analytical and hypothetical. It freezes the live scenario identity, infrastructure revision, active manual closures, resources and original plan before applying counterfactual changes in an isolated store. Original-plan feasibility is reported separately from reoptimized alternatives. It does not approve a plan, issue a mission command or modify live closure records.

The recorded extreme synthetic benchmark had two baseline assignments at its initial state; by its later horizon, both original routes were unsupported and all 72 candidate destinations were unserved. When all ten modeled corridors were closed, reoptimization returned zero assignments. Missing ML evidence, unsupported labels, limited resources, flooded segments, closed bridges and access-graph disconnection can all reduce coverage. A zero assignment or no-safe-route response is retained as failure evidence, not reinterpreted as success.

## Limitations

- All locations, people, labels, infrastructure, flood conditions and routing speeds are synthetic.
- The ten-case suite is small and designed for condition coverage, not statistical inference.
- The classifier is evaluated on labels from the same simulator family that generated its training data.
- The road graph is generated geometry; route reachability is not surveyed road access or a safety assessment.
- Greedy baseline comparisons are specific to the documented objective, generated routes and inventory.
- No real incident, emergency service, communications, hydraulic calibration or field exercise is represented.

Supporting artifacts: [reproducible commands and measurements](REPRODUCIBLE_BENCHMARKS.md), [Part 12 model verification](PART_12_VERIFICATION.md), [Part 13 robustness verification](PART_13_VERIFICATION.md), [Part 14 mission acceptance](PART_14_VERIFICATION.md).
