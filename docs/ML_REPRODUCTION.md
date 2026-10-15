# Reproduce the local ML experiment

From the repository root, install backend dependencies into a local virtual environment, then run from `backend/`:

```powershell
python -m pip install -r requirements.txt
python -m app.ml.generate_dataset
python -m app.ml.train
```

The generator writes an ignored CSV to `backend/data/ml/flood_exposure.csv` and tracked provenance metadata to `backend/ml_artifacts/dataset_metadata.json`. Training validates columns and finite values, splits by scenario ID, compares baselines/candidates, writes model metadata and the compressed artifact, saves actual evaluation metrics and an SVG plot, and reports grouped split IDs. The default random states are in the saved metadata and script.

Then run the API from `backend/` with `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`. The frontend calls only local versioned API endpoints. Inference checks the artifact hash, feature ordering, flood engine version and scikit-learn version. It does not retrain automatically.

To verify in the UI, open Model Intelligence Lab for saved metrics and the active scenario inspector. In Command Center, enable Layers → `predictedRisk` to highlight model-predicted future exposed buildings in orange; the current flood palette remains physically simulated exposure. The score is uncalibrated, and all targets are synthetic.

For a visible flood demo, run `python -m app.ml.demo_scenario` from `backend/`. It creates a new scenario in the configured local SQLite store (seed 2026; rainfall 100 mm/h; stage 0.8 m; drainage 0.4) and advances six real simulation ticks. The measured reference run reaches 0.311 m maximum land depth, 18 affected buildings, 6 exposed roads, and 6 closed bridges. The values are backend simulation results, not a visual animation. A fresh scenario is created each time.
