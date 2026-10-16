# Conventional and RESQ-AI Assignment Comparison

## Shared feasible set

Both methods receive the same scenario snapshot, destination priorities, unit inventory, vehicle compatibility, capacity, flood-aware graph routes, manual closures and synthetic travel assumptions. Unreachable unit/destination pairs are excluded from both methods. Each unit and each destination may be assigned at most once.

## Baseline

The conventional baseline considers destinations in descending priority order with a stable ID tie-break, then assigns the nearest compatible unused unit by graph-route distance with a stable unit ID tie-break. It is a conventional heuristic, not a deliberately weakened straw baseline.

## Optimized assignment

The optimized method uses SciPy `linear_sum_assignment` on a deterministic score matrix, with stable sorting and a tiny deterministic lexicographic tie-break. The declared objective is:

`Σ(priority_score × min(unit_capacity, occupants) / max(occupants, 1)) − 0.15 × Σ(synthetic_route_minutes)`

Infeasible pairs receive a prohibitive cost and are never returned as assignments. The solver status reports the algorithm actually used. This objective trades priority-weighted occupant coverage against total synthetic route time; it does not guarantee that every route or coverage measure improves independently.

## Reported metrics and units

- **Destinations covered:** count of assigned destinations.
- **Priority-weighted coverage:** score points, summing priority score times the occupant fraction targeted within unit capacity.
- **Occupants targeted:** synthetic people covered within the selected units' per-mission capacities.
- **Total route distance:** sum of assigned graph route lengths, meters.
- **Total simulated travel minutes:** sum of synthetic travel minutes across assigned missions. This is a sum, not the maximum arrival time.
- **Maximum estimated arrival:** greatest synthetic route time among assigned missions.
- **Resource utilization:** assigned units divided by configured available units; zero if none are available.
- **Unreachable destinations:** count of destinations with no feasible route/assignment, reported independently from unassigned reachable destinations.
- **Available/reserved units:** experiment inventory counts; experiments have no live operational reservations.
- **Objective value:** the formula above, with score-points/minutes as its declared trade-off scale.

Every baseline-to-optimized delta is computed from the selected saved result. Positive values are not automatically improvements: the UI must interpret route time/distance regressions as worse and coverage/objective gains as better. All routes, capacities, travel speeds, priorities and occupants are synthetic and unvalidated for real dispatch.
