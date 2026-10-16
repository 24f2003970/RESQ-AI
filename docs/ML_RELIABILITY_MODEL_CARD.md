# Model card — synthetic future building exposure v1

## Intended use

Local demonstration and decision-support evidence in the RESQ-AI synthetic Digital Twin. Given a generated city's current state, the model estimates whether each building footprint's simulated water depth reaches 0.05 m after six fixed five-minute flood ticks (30 simulated minutes).

It is not an operational forecast, public warning, rescue dispatch authority, or estimate of real-world probability of harm.

## Data and training

- 72 generated scenarios, 25,920 observations, 72 buildings per scenario at five observation ticks.
- Scenario-grouped split: 42 training, 15 validation, 15 final test groups. No scenario crosses partitions.
- Labels come from the deterministic flood engine. No observed disaster data were used.
- 25 current-state/forcing/building features with documented units in `backend/ml_artifacts/dataset_metadata.json`.
- Random forest: 64 trees with bounded depth and leaf size. The existing v1 model artifact is unchanged.

## Calibration

A Platt sigmoid calibrator is fit from scenario-grouped out-of-fold scores from development groups. It is adopted only after nested group evaluation improves Brier score by at least .001 without worsening log loss by more than .01. Its output is labeled **calibrated synthetic probability** and only describes the synthetic target under this simulator's generated distribution.

## Evaluation

Held-out synthetic test F1 .9660; precision .9783; recall .9541; balanced accuracy .9631; ROC-AUC .9945; average precision .9960. Raw/calibrated Brier: .03053/.02792; log loss: .10667/.09419; ECE: .02654/.00501 using 10 fixed-width bins. See `ML_EVALUATION.md` and `backend/ml_artifacts/reliability_evaluation.json` for exact values and failures.

## Important limits

The held-out test uses seeds from the same simulator and similar generator. The result does not establish real-world accuracy. Spatially repeated building layouts and deterministic physics may make the task easier than real operations. The calibrator inherits that scope. Feature-wise support status is not a guarantee of accuracy and cannot identify every hazard. False negatives, false positives, distribution shift, missing artifacts and stale results remain possible. Physics simulation is authoritative for current modeled water. Human commander approval remains mandatory for rescue plans.
