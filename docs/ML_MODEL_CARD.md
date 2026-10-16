# Model card: future synthetic building exposure

> Part 12 reliability/calibration supplement: [`ML_RELIABILITY_MODEL_CARD.md`](ML_RELIABILITY_MODEL_CARD.md). Calibrated outputs describe only held-out synthetic scenario behavior. Feature support is a warning, not an accuracy guarantee.

## Intended use

Demonstrate a local ML inference path alongside the RESQ-AI synthetic Digital Twin. Given a generated city's current simulated state, estimate whether each building's footprint reaches at least 0.05 m of water six five-minute ticks (30 simulated minutes) later.

## Model details

- Name/version: RESQ-AI Future Building Exposure Classifier 1.0.0.
- Algorithm: scikit-learn RandomForestClassifier, 64 trees, bounded tree depth and leaf size.
- Artifact: `backend/ml_artifacts/flood_exposure_v1.joblib` (SHA-256 recorded in `model_metadata.json`).
- Features: current flood grid and local terrain, scenario forcing, simulation tick, and generated building attributes.
- Output: binary predicted exposure and raw score; when validated Part 12 artifacts load, a separately labeled Platt-calibrated synthetic estimate is also available.

## Data

25,920 labeled observations from 72 independently seeded simulated scenarios, five observation times and 72 buildings per scenario. Flood engine outputs create the labels. No observed floods or real city measurements were used.

## Evaluation

Scenario-grouped split: 42 training groups, 15 validation groups, 15 held-out test groups. Test F1 is 0.966, precision 0.978, recall 0.954, balanced accuracy 0.963, ROC-AUC 0.994, and average precision 0.996. The transparent heuristic test F1 is 0.937; the prior DummyClassifier F1 is 0.725. See `ML_EVALUATION.md` and the saved evaluation JSON for full details.

## Limitations and risks

The model learns a deterministic synthetic simulator and its assumptions. A high test score over generated scenarios does not show performance on real weather, terrain, infrastructure, or disasters. Spatially correlated buildings and repeated configurations can make this synthetic task easier than deployment. Raw scores are uncalibrated; the separate Part 12 transformation is calibrated only against held-out synthetic scenarios. Feature importance is global and noncausal, and false negatives or positives remain possible. The physical simulator remains authoritative for water state; the estimate must not be used as operational dispatch or public warning advice.

## Maintenance

Regenerate data and train only through the documented offline commands. Any change to features or flood engine version should result in a new dataset/model artifact and fresh grouped test evaluation. The runtime checks model checksum and compatibility before inference.
