# Synthetic score calibration

## Method and adoption gate

Raw random-forest scores are transformed with a one-dimensional Platt sigmoid (logistic regression over clipped score logits). The development adoption evaluation is fully nested and scenario-grouped. For each of five outer folds, the base estimator is fit only on outer-training scenarios; five inner grouped folds produce OOF scores for those same outer-training scenarios; and Platt is fit only on those inner OOF scores and labels. The outer model then scores its held-out scenarios, and both raw and calibrated predictions are evaluated there. The saved `nested_group_fold_audit` lists outer validation, estimator-fit, inner OOF estimator-fit, and calibrator-fit groups for each fold.

The predetermined gate adopts only when the aggregate outer-fold Brier score improves by at least .001 and log loss is no more than .01 worse. On this run, development Brier was .0321893 raw and .0297926 calibrated, an improvement of .0023966. Development log loss was .1133040 raw and .1023491 calibrated (delta −.0109549), so the gate adopted calibration. No outer validation group enters any estimator or calibrator fit used to predict that fold.

After the adoption decision, the production Platt calibrator is refit on five-fold grouped OOF scores over the complete development partition (42 train plus 15 validation scenarios). The original random-forest artifact is preserved. The final 15 scenario groups remain untouched by fitting and adoption.

## Final synthetic test measurements

The unchanged 5,400-row final synthetic test set was evaluated after the development-only decision. Raw vs adopted Platt Brier was .030526 vs .027917, log loss .106666 vs .094190, and 10 fixed-width-bin ECE .026538 vs .005009. At threshold .5, raw F1 was .966040 and calibrated F1 was .966182. Since Platt is monotone, ROC-AUC remained .994494. These are final synthetic test measurements, not development adoption metrics. Reliability diagrams use empirical positive frequency against mean score per fixed-width [0,1] bin; empty bins are omitted from weighted ECE and bin counts are retained.

These values are calibration against held-out synthetic scenarios, not real-world probability validation. Do not describe the output as real disaster probability or confidence in a rescue outcome. A failed development gate removes the production calibrator artifact; missing or incompatible calibration artifacts result in explicit degraded status and raw-score labeling.

Reproduce with `python -m app.ml.reliability --dataset <generated-csv> --artifacts ml_artifacts` from `backend/`.
