# Flood simulation sensitivity evaluation

`backend/app/ml/sensitivity.py` chooses validation scenarios only and reruns the authoritative flood engine from each selected initial condition. It compares baseline predictions with six bounded interventions: rainfall +5 and +30 mm/h, river stage +0.03 and +0.15 m, and drainage effectiveness -0.05 and -0.20 (clipped to valid simulator limits), at ticks 0, 6, and 12. The held-out test scenarios are never used for sensitivity selection.

The saved run contains 63 scenario/tick/variant comparisons. Mean nonbaseline prediction flip fraction was .023663. Mean Spearman rank correlation was .904420 among defined pairs; 30 comparisons had undefined rank correlation because all outputs were tied/constant. Changes to inputs that push every building outside observed support are explicitly marked. Sensitivity is neither accuracy nor evidence that a stable prediction is correct; simulator outcomes and support statuses are retained for interpretation.

Run from `backend/`: `python -m app.ml.sensitivity --dataset-metadata ml_artifacts/dataset_metadata.json --artifacts ml_artifacts`. Local runtime was approximately 3.2 seconds for the recorded experiment; hardware-specific.
