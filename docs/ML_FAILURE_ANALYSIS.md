# Synthetic failure and subgroup analysis

The reproducible report `backend/ml_artifacts/reliability_evaluation.json` stores held-out false positives and false negatives with scenario IDs, inputs, and scores. In the 5,400-row test set there were 65 false positives and 141 false negatives (TN 2,264, TP 2,930). A false negative means the model missed the simulator's 30-minute target for that row; it does not establish a real incident miss.

For currently dry buildings (current footprint max depth below 0.05 m), 3,648 rows across 15 scenarios included 1,319 newly exposed positives. Precision was .947707, recall .893101, F1 .919594; there were 141 false negatives. This is materially lower recall/F1 than the full set and deserves attention in the demo.

Subgroups include rainfall, river stage, drainage, terrain and distance quantiles, near-threshold rows, current dry/newly exposed classes, and simulation tick. Metrics are emitted only when at least three scenarios and both target classes are represented; otherwise the artifact gives counts/status only. Groups remain correlated within scenario, so row counts are not independent sample counts. Small subgroup metrics are descriptive, not confidence intervals or deployment estimates.

The model is trained and tested on deterministic synthetic data; no real-world validation was performed. Global error examples and subgroup performance should be used to discuss limits, not imply causal explanations.
