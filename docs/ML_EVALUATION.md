# Part 4 model evaluation

Source of record: `backend/ml_artifacts/evaluation.json`, generated from the final held-out scenarios by `backend/app/ml/train.py`. Metrics below are rounded for readability.

## Task and split

The binary target is footprint maximum water depth ≥ 0.05 m six fixed five-minute steps after the current observation. There are 72 independent scenario IDs. GroupShuffleSplit creates 42 training, 15 validation, and 15 test scenario groups. Rows from a scenario never cross partitions. Test data contains 5,400 observations: 2,329 negative and 3,071 positive. The model is selected on validation F1, then PR-AUC and balanced accuracy, and refit on training plus validation; test outcomes do not select the model.

## Held-out test results

| Model | Precision | Recall | F1 | Balanced accuracy | ROC-AUC | Average precision |
|---|---:|---:|---:|---:|---:|---:|
| Random forest (selected) | 0.978 | 0.954 | 0.966 | 0.963 | 0.994 | 0.996 |
| Transparent heuristic | 0.901 | 0.975 | 0.937 | 0.917 | 0.977 | 0.979 |
| Dummy prior | 0.569 | 1.000 | 0.725 | 0.500 | — | — |

Random forest confusion matrix: TN 2,264; FP 65; FN 141; TP 2,930. The uncalibrated Brier score is 0.031 and must not be interpreted as probability calibration. The estimator scores are not presented to users as probabilities.

## Model selection and runtime

Validation compared logistic regression, decision trees of depth 5 and 9, and a bounded 64-tree random forest, in addition to the Dummy and transparent heuristic baselines. The random forest was selected by the recorded validation ranking. Measured prediction latency is 0.00229 ms per observation, averaged over 25 repetitions on batches of 5,400 rows on the development machine; it is a local microbenchmark, not a laptop-wide guarantee. Artifact size is approximately 1.15 MB.

## Interpretation

The selected model exceeds the heuristic on this generated test set, but it only demonstrates generalization across held-out seeds within the same synthetic simulator. It is not evidence of generalization to real floods. Failure examples and test-set permutation importance are saved with the evaluation report. Global permutation importance is descriptive, not a causal or individual explanation.
