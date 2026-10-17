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

A Platt sigmoid calibrator is adopted only after fully nested scenario-grouped development evaluation: each outer-fold base estimator and calibrator use outer-training groups only, with inner grouped OOF scores used for Platt fitting. The fixed gate requires at least .001 Brier improvement and no more than .01 log-loss regression. After that decision, the production calibrator is refit on grouped OOF scores across all development groups. This run's nested development Brier was .03219 raw / .02979 calibrated; log loss was .11330 / .10235. Its output is labeled **calibrated synthetic probability** and only describes the synthetic target under this simulator's generated distribution.

## Evaluation

Final synthetic test metrics are reported separately from the development adoption gate. Test F1 .9660; precision .9783; recall .9541; balanced accuracy .9631; ROC-AUC .9945; average precision .9960. Raw/calibrated Brier: .03053/.02792; log loss: .10667/.09419; ECE: .02654/.00501 using 10 fixed-width bins. The untouched test split did not select or fit calibration. See `ML_EVALUATION.md` and `backend/ml_artifacts/reliability_evaluation.json` for exact values, split audit, artifact hashes, and failures.

## Important limits

The held-out test uses seeds from the same simulator and similar generator. The result does not establish real-world accuracy. Spatially repeated building layouts and deterministic physics may make the task easier than real operations. The calibrator inherits that scope. Feature-wise support status is not a guarantee of accuracy and cannot identify every hazard. False negatives, false positives, distribution shift, missing artifacts and stale results remain possible. Physics simulation is authoritative for current modeled water. Human commander approval remains mandatory for rescue plans.
