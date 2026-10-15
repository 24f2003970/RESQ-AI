# Dataset provenance

## Source and generation

The training table is generated entirely locally by `backend/app/ml/dataset.py`. It invokes the RESQ-AI deterministic city generator and Part 3 flood engine. No downloaded dataset, hosted inference, API key, or real incident record is used.

The default run samples 72 independent scenario forcing configurations from sampling seed 44117. Each scenario seed is an integer from 73000 through 73071. Rainfall is sampled from 0–260 mm/h, river stage from −0.7–1.8 m, and drainage effectiveness from 0.05–1.0; each stays constant within a generated scenario. Five observations are taken at ticks 0, 3, 6, 9 and 12 for each of 72 generated buildings. The label is computed by the same flood engine after six additional ticks.

## Fields and leakage controls

There are 25 input features, documented with units in `backend/ml_artifacts/dataset_metadata.json`. They describe only the observation-time state: current and neighborhood water depth, terrain, canal/stage/rain/drainage conditions, tick, and building location/shape/use. Scenario ID, seed, building ID, future water depth and future exposure are not model inputs. IDs remain in the CSV solely for grouping and traceability.

The saved dataset contains 25,920 observations: 17,298 positive and 8,622 negative labels, with zero duplicate feature/target rows detected by the generator. These counts are properties of this generator run, not a representative estimate of real-world flood prevalence. The manageable CSV is ignored by git; metadata, training source, evaluation, and model artifact are tracked.

## Reproduction

Run `python -m app.ml.generate_dataset` from `backend/`. The default command writes `backend/data/ml/flood_exposure.csv` and refreshes `backend/ml_artifacts/dataset_metadata.json`. Use the generator's `DatasetConfig` to alter counts or seeds in local development. See `ML_REPRODUCTION.md` for end-to-end instructions.
