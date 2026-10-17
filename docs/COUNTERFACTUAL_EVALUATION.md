# Counterfactual Evaluation Method

## Intervention categories

- **Baseline:** no intervention; evaluated at the same configured horizon as the other conditions.
- **Environment:** change rainfall, river stage and/or drainage. At least one simulator tick is required; the deterministic flood engine recomputes depth and physical impacts.
- **Road closure:** close one or more existing road IDs in the analytical graph only.
- **Bridge closure:** close existing bridge IDs by changing only their bridge impact in the analytical snapshot. The current graph models bridge closure at the bridge span.
- **Resources:** remove explicit frozen standby unit IDs, or a deterministic number of a selected ground-unit type. The available set cannot exceed the generated inventory.
- **ML reliability:** use current reliability metadata, explicitly inject model unavailability, filter out-of-support predictions through the existing support policy, or explicitly suppress forecast-only eligibility for one analytical failure case.

Each study accepts at most 12 conditions and at most 12 evaluation ticks. The 11-case benchmark in this release has 10 interventions plus an unchanged-inventory analysis; conditions are deterministic cases, not equally likely events.

## Evaluation sequence

For each condition, physical state is recomputed first. The exact manually closed road set from the frozen live baseline is unioned with the condition's hypothetical closures, including baseline, environmental, resource, bridge, and critical-dependency analyses. The saved original plan is then checked assignment by assignment. Route edges must exist in the counterfactual graph and must not be closed, flooded, manually blocked, or exceed the unit's depth limit; units must remain supported and available; destinations must remain reachable. Specific reasons are recorded. No original assignment is silently changed. Frozen closures are analytical inputs and do not mutate operational closure records.

The counterfactual plan is computed separately with the existing priority, routing and SciPy assignment implementations. This objective is the current system objective: sum of destination priority score times the fraction of occupants covered by the assigned unit capacity, minus 0.15 times synthetic route minutes. One unit and one destination can each appear at most once. The optimizer may leave units unused.

## Fairness and limitations

Physical flood state is authoritative for road/building accessibility. Part 12 model labels describe synthetic simulator outcomes only; calibrated values are not real disaster probabilities. Model failure or out-of-support evidence triggers transparency and fallback, not fabricated confidence. Environmental changes can alter the eligible destination set and priorities, so the matrix gives each condition’s coverage denominator.

Routes use the project’s synthetic graph, synthetic speeds and documented unit/building access spurs. Ground-unit access requires attachment to a traversable road-network component; access spurs alone cannot connect isolated nodes or bypass a closed corridor. Co-located points are supported only when they are already on the same open network node. The graph is not a surveyed road network, bridge engineering model, traffic model, or field-safety determination. A result means “supported under this simulator’s assumptions,” not “safe to dispatch.”
