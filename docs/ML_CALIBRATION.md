# Synthetic score calibration

## Method

Raw random-forest scores are transformed with a one-dimensional Platt sigmoid (logistic regression over clipped score logits). Calibration data are generated from scenario-grouped out-of-fold predictions: folds are grouped by scenario, and final test scenario IDs never enter fitting or method selection. Scenario-equal sample weighting limits domination by scenarios with more sampled rows. Adoption is gated by nested GroupKFold development evaluation: Brier improvement must be at least .001 and log loss may not regress by more than .01.

## Measurements

On the untouched 5,400-row synthetic test set, raw vs Platt Brier was .030526 vs .027917, log loss .106666 vs .094190, and 10 fixed-width-bin ECE .026538 vs .005009. At threshold .5, raw F1 .966040 and calibrated F1 .966182. Since Platt is monotone, ROC-AUC remained .994494. Reliability diagrams use empirical positive frequency against mean score per fixed-width [0,1] bin; empty bins are omitted from weighted ECE and bin counts are retained.

These values are calibration against held-out synthetic scenarios, not real-world probability validation. Do not describe the output as real disaster probability or confidence in a rescue outcome. Missing or incompatible calibrator artifacts result in an explicit degraded status and raw score labeling.

Reproduce with `python -m app.ml.reliability --dataset <generated-csv> --artifacts ml_artifacts` from `backend/`.
