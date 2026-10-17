# RESQ-AI · technical deep-dive notes

Use this for technical judges or Q&A follow-up. Keep synthetic assumptions in view.

1. **State ownership.** `ScenarioStore` owns versioned scenario snapshots, event history and checkpoints in SQLite. A process lock and immediate transactions guard writes. Replay reconstructs a selected tick without triggering agents.
2. **Flood calculation.** `backend/app/flood.py` advances a bounded grid in fixed five-minute steps. The method uses deterministic inputs and mass accounting. See `FLOOD_SIMULATION_METHOD.md`; its assumptions are not hydraulic validation.
3. **Model.** `backend/app/ml/` generates grouped samples, trains the fixed random forest, checks integrity and builds local inference features. Target is synthetic future exposure six ticks later. Grouped splits prevent observations from the same synthetic scenario appearing in both evaluation partitions.
4. **Calibration.** `backend/app/ml/reliability.py` performs nested grouped validation for adoption. For each outer fold, inner grouped OOF scores train a calibrator; the outer estimator is fit only to outer-training groups. Final production Platt fitting uses OOF predictions over development groups after adoption. The final test groups do not enter fitting or gate choice.
5. **Support.** Saved marginal feature bounds label within, edge and out-of-support rows. They disclose limits; they cannot prove joint-distribution plausibility or real-world reliability.
6. **Agent trace.** `backend/app/agents.py` claims durable events, deduplicates agent runs, validates epoch/version/revision and saves outputs. The commander stage creates a proposal; the human review endpoint separately approves/rejects.
7. **Routing.** `backend/app/rescue.py` splits corridors at intersections and bridge spans, filters edges using flood and closure policy, and requires unit/destination access to a traversable component. Boat routing is explicitly unsupported.
8. **Assignment.** SciPy `linear_sum_assignment` optimizes the declared additive utility for the given route map. It does not optimize an uncertain real-world response objective. The baseline is a deterministic nearest feasible assignment over the same ranking and route map.
9. **Mission operation.** `backend/app/missions.py` persists mission status, resource reservation, route polyline and traveled-distance progress. Dispatch is explicit. Closure can block only a remaining route edge. Mid-route rerouting uses saved current geometry/progress. Route approvals validate scenario and infrastructure state. Completion and return-to-service are explicit commands.
10. **Counterfactual isolation.** Scenario Lab and Robustness Lab use separate analytical stores, deterministic snapshots and existing engine functions; they do not write human approvals, reservations or live operational mission commands.
11. **Frontend role.** React/TypeScript consumes versioned backend state. React Three Fiber renders the Digital Twin and vehicle movement along the backend route polyline. Display interpolation is not authority to move a mission.
12. **Reproduction.** Run the acceptance commands in `PART_15_VERIFICATION.md`; use the disposable runner commands. The Part 15 JSON report includes environment, seeds, per-case metrics, solver state, timing and model artifact checksums.

The five-minute talk should spend no more than a minute on low-level implementation. Use the architecture diagram and bring up these details only when asked.
