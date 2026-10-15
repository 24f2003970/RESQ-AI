# Part 4 implementation

Part 4 adds an original, locally trained scikit-learn model for synthetic future building exposure. It does not replace the physical flood engine and does not claim observed disaster prediction.

## Prediction task

For each generated building, use only the current scenario state to predict whether maximum water depth over its footprint will reach 0.05 m after six fixed five-minute flood ticks. The result is a binary 30-minute future exposure estimate. Current simulation exposure, ML future exposure, and rescue priority remain separate concepts.

The 25 features include present footprint and neighborhood water, local terrain, canal distance and stage, rainfall and drainage, current tick, building geometry and use. Scenario IDs and future state are excluded. The dataset target is derived by advancing the same deterministic flood engine six ticks from each observation.

## Data and model

`backend/app/ml/dataset.py` builds 72 independent scenario groups and five observations per group for 72 buildings, for 25,920 rows. Sampling seed is 44117; scenario seeds are 73000 through 73071. The ignored CSV can be regenerated locally. Dataset provenance is saved in `backend/ml_artifacts/dataset_metadata.json`.

Training compares a prior DummyClassifier, a transparent heuristic, logistic regression, depth-limited decision trees, and a 64-tree random forest. Validation chooses the practical model by F1, then PR-AUC, then balanced accuracy. Splits are by scenario group: 42 train, 15 validation, 15 test. The final estimator is refit on train plus validation only. The saved test remains unseen for final reporting.

The model artifact and metadata are in `backend/ml_artifacts/`. Inference verifies SHA-256, ordered feature schema, engine version, and scikit-learn version before loading. Inference uses the saved scenario state and current physical flood grid. Responses include scenario ID, state version, tick, current impact and future label. Global test-set permutation importances are explicitly not local causal explanations.

## API and user interface

Versioned read-only endpoints expose model status, dataset metadata, evaluation, feature definitions, whole-scenario predictions and a selected building prediction. OpenAPI schemas and generated TypeScript types are checked at runtime in the frontend.

The Model Intelligence Lab displays saved test metrics and baselines, confusion counts, global feature importance, provenance, limitations and prediction inspection. Command Center displays the exposed-building count and selected-building estimate. A separate 3D layer colors predicted future exposure without altering current simulation colors. Predictions are cleared on scenario version/tick change, and older responses are discarded.

## Scope boundaries

All results are generated from a fictional deterministic simulation. The high synthetic held-out score is not real-world accuracy. Model scores are uncalibrated, so the UI does not call them probabilities. There is no cloud inference, API key, or automatic retraining. Part 5 is not included.
