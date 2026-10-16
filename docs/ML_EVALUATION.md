# Part 4 baseline and Part 12 reliability evaluation

Source of record: `backend/ml_artifacts/evaluation.json`, generated from the final held-out scenarios by `backend/app/ml/train.py`. Metrics below are rounded for readability.

## Task and split

The binary target is footprint maximum water depth ≥ 0.05 m six fixed five-minute steps after the current observation. There are 72 independent scenario IDs. GroupShuffleSplit creates 42 training, 15 validation, and 15 test scenario groups. Rows from a scenario never cross partitions. Test data contains 5,400 observations: 2,329 negative and 3,071 positive. The model is selected on validation F1, then PR-AUC and balanced accuracy, and refit on training plus validation; test outcomes do not select the model.

## Original held-out test results

| Model | Precision | Recall | F1 | Balanced accuracy | ROC-AUC | Average precision |
|---|---:|---:|---:|---:|---:|---:|
| Random forest (selected) | 0.978 | 0.954 | 0.966 | 0.963 | 0.994 | 0.996 |
| Transparent heuristic | 0.901 | 0.975 | 0.937 | 0.917 | 0.977 | 0.979 |
| Dummy prior | 0.569 | 1.000 | 0.725 | 0.500 | — | — |

Random forest confusion matrix: TN 2,264; FP 65; FN 141; TP 2,930. Raw scores are uncalibrated and are not probabilities. Part 12 separately adds a Platt-calibrated synthetic estimate after grouped development fitting and integrity checks; see the results below.

## Model selection and runtime

Validation compared logistic regression, decision trees of depth 5 and 9, and a bounded 64-tree random forest, in addition to the Dummy and transparent heuristic baselines. The random forest was selected by the recorded validation ranking. Measured prediction latency is 0.00229 ms per observation, averaged over 25 repetitions on batches of 5,400 rows on the development machine; it is a local microbenchmark, not a laptop-wide guarantee. Artifact size is approximately 1.15 MB.

## Interpretation

The selected model exceeds the heuristic on this generated test set, but it only demonstrates generalization across held-out seeds within the same synthetic simulator. It is not evidence of generalization to real floods. The Part 12 Platt calibrator is trained only from grouped development folds and adopted by a nested development gate. On the untouched test, raw vs calibrated Brier is 0.030526 vs 0.027917, log loss 0.106666 vs 0.094190, and 10-bin ECE 0.026538 vs 0.005009. See `ML_CALIBRATION.md`, `ML_FAILURE_ANALYSIS.md`, and `backend/ml_artifacts/reliability_evaluation.json` for calibration curves, failures, support counts, and subgroup metrics. Global permutation importance is descriptive, not a causal or individual explanation.
