# Distribution support and shift warnings

RESQ-AI uses an interpretable per-feature support check rather than an opaque novelty score. For each required feature, metadata fit on train plus validation observations records finite min/max and 0.5/99.5 percentiles. Missing/nonfinite or incompatible feature schemas are reported separately. A record is `outside_observed_support` if any feature falls outside min/max; it is `edge_of_observed_support` when outside the central quantile interval but still within min/max; otherwise it is `within_observed_support`.

The final test split had 4,540 within-support observations, 125 edge cases, and 735 outside min/max (13.6%). This demonstrates the warning is actionable on held-out synthetic seeds, not that it detects all unsafe conditions. Within-support does not imply the prediction is correct. Missing model/calibrator or schema mismatch is reported as unavailable/degraded, not as an OOD score.

Unsupported future labels are excluded from rescue destination eligibility and agent forecast evidence. Current physics-simulator exposure remains available. Support statistics, feature names, thresholds, and provenance are stored in `backend/ml_artifacts/distribution_support_v1.json`.
