# Reliability demo guide

1. Open **Model Intelligence Lab → Reliability & Uncertainty**. Explain that the target is synthetic building exposure six five-minute ticks ahead.
2. Show raw and Platt calibration diagrams and Brier/log-loss/ECE values. Say “calibrated against held-out synthetic scenarios,” never “real flood probability.”
3. Open one false negative and compare its scenario/input features. Point out the lower recall among currently dry buildings that later become exposed.
4. Show support counts and select an outside-support case. Explain that outside support is a warning, while in-range does not guarantee correctness.
5. Compare a validation-only rainfall, river, or drainage variant. Explain the flood engine reruns from the initial state and that sensitivity does not prove accuracy.
6. In the building inspector, distinguish current physical flood state from a future ML estimate and show its horizon, calibration label, and support status.
7. Open Agent Explorer/Judge Mode. Show reliability status and warnings in the trace. Clarify unsupported ML labels are excluded from future forecast planning evidence; physical flood state remains authoritative and commanders approve rescue plans.
8. Mention synthetic-only data, no real-world validation, and that local timing depends on hardware.

The reliability API serves saved artifacts; it does not rerun report generation on each page refresh. The UI displays computed artifact evidence and does not invent confidence percentages.
