# Flood Risk Model Strategy

## Scope and scientific claim

Train one local scikit-learn classifier for a narrowly defined **synthetic scenario risk class**. Its purpose in the first demo is to exercise a reproducible training, evaluation, loading, and explanation pipeline and to compare learned scores with a transparent rule baseline. It does not forecast real floods and is not validated for emergency use.

Keep the flood progression process model separate: it advances the fictional water grid. The classifier estimates the class assigned by the chosen training-label source from a scenario snapshot. If labels come from the simulator, the model is learning to approximate simulator-derived labels; show that provenance in the UI and do not present its performance as field accuracy.

## MVP target and inputs

Suggested target: per-building simulated exposure class at a fixed scenario horizon, derived from simulator depth and a disclosed vulnerability rule (for example, low/moderate/high/critical bands). Freeze and version the exact threshold table before generating labels. Do not use future values or target-derived fields as features.

Candidate snapshot features: local elevation, distance to river, current/lagged simulated depth, recent depth change, rainfall intensity and accumulation, river stage, building use/floors, declared occupancy/vulnerability, distance to nearest passable road, and facility proximity. Only features available at prediction time are admissible. Numeric units, missing-value rules, and categorical encodings are persisted with the model.

## Training data and provenance

### MVP

Generate data from the deterministic flood simulator across documented ranges of seeds and scenario parameters. Save a manifest with generator/solver version, seed, parameter ranges, target thresholds, sample count, generation time, and hashes. Keep generated bulk files out of Git; commit the small manifest and a tiny reviewed fixture if needed. Split by **scenario seed / event group**, not by individual neighboring building rows, to reduce spatial and scenario leakage. Freeze a test seed set before model selection.

### Public data candidates for a later separate experiment

| Source | Useful evidence | Fit and constraint |
|---|---|---|
| [Sen1Floods11](https://github.com/cloudtostreet/Sen1Floods11) | Sentinel-1 imagery with manually classified flood/water masks over a limited set of events | Useful for pixel-level flood extent experiments, but labels do not directly describe building damage, depth, or rescue priority. Inspect the current download source and license before redistributing; the accessible dataset mirror carries Apache 2.0 terms, which may not establish terms for every upstream artifact. |
| [Copernicus CEMS flood data](https://cds.climate.copernicus.eu/licences/cems-floods) | Flood early warning/monitoring products and event information | Public use is permitted under the published service terms with attribution and no warranty; individual third-party inputs may have separate terms. Geographic coverage and target semantics must match the task. |
| [NASA GPM IMERG](https://gpm.nasa.gov/data/imerg) | Precipitation estimates at roughly 0.1° / 10 km scale, with half-hourly and other products | Can inform rainfall context, not label city-block flood depth. Product versions, latency, file format, and usage/citation instructions must be recorded. |

These are candidates, not downloaded or included training data. Before using one, inspect the exact product's metadata, terms, version, access requirements, spatial/temporal resolution, and attribution. Do not combine incompatible labels or infer building-level labels from coarse rain estimates.

## Pipeline

1. Validate manifest, schema, units, unique sample keys, and target source.
2. Reject non-finite or impossible values; report counts and reasons. Preserve a raw manifest and produce deterministic processed tables.
3. Split by full seed/scenario/event groups into train, validation, and locked test partitions; use a fixed split manifest.
4. Establish a majority-class baseline and a rule-based threshold baseline before fitting ML.
5. Start with class-weighted RandomForest or HistGradientBoosting from scikit-learn; choose one only after comparing validation macro-F1 and critical-class recall with the transparent baseline. Do not add XGBoost unless it demonstrably helps within install/time constraints.
6. Tune only on training/validation groups. Keep test data untouched until the model and threshold policy are fixed.
7. Save model, preprocessing pipeline, feature schema, library versions, seed, split manifest hash, label definition, and training metrics together. Load only a local artifact with a matching schema/version.
8. Reproduce a training run from one command and fixed seed; report package versions and artifact hash.

## Evaluation

Report class counts, confusion matrix, balanced accuracy, macro-F1, per-class precision/recall, and critical-class precision-recall (average precision) where support permits. Include confidence intervals or per-seed distributions where sample counts allow. Compare to both baselines on the identical locked test scenarios. Measure calibration only if probabilities are used for decisions. Never compare random row splits with grouped test splits as if they were equivalent.

Test generalization by holding out whole seeds, rainfall patterns, river stages, and, where feasible, one scenario family. A synthetic test only measures generalization within the generator's assumptions.

## Explainability and use

Use permutation importance on the grouped validation set and show feature definitions/units. For an individual decision, show actual feature values and model probabilities next to the rule baseline; avoid describing correlation-based importance as causal. Add a model card stating target source, split grouping, evaluation, intended demonstration use, and known limitations.

The classifier contributes a risk estimate; the priority agent combines risk with exposure, vulnerability, and reachability using explicit weights. Risk scores alone never commit missions. The operator can inspect and reject the proposed plan.

## Risks and mitigations

- **Circular simulation labels:** call them simulator-derived labels; evaluate agreement with the generating rule and do not claim real-world predictive skill.
- **Leakage across neighboring cells/scenarios:** group splits by seed/event and freeze test groups.
- **Unstable or rare critical class:** disclose support; use class weights; do not hide per-class metrics.
- **Mismatched public data:** keep remote sensing flood extent as a distinct task unless labels and spatial scale support the target.
- **No network at demo:** train and package the small local artifact beforehand; verify inference without network and provide transparent rule fallback if the artifact is absent.
