# Robustness Metric Definitions

| Metric | Definition |
| --- | --- |
| Reachable priority destinations | Distinct eligible destination IDs with at least one compatible route in the saved planner route map; reachability means synthetic graph connectivity under the documented access-spur and unit-depth assumptions. |
| Assigned destinations | Distinct destination IDs assigned in the optimized plan. |
| Priority-weighted coverage | Sum of `priority_score × occupants_targeted / max(destination occupants, 1)` over optimized assignments. |
| Coverage denominator | Sum of condition-specific eligible destination priority scores. It is shown because environmental conditions may change eligibility and priority. |
| Assigned route distance | Sum of synthetic planner distances for optimized assignments. |
| Maximum synthetic arrival | Maximum synthetic travel minutes over assigned routes. |
| Travel-time sum | Sum of synthetic travel minutes over assigned routes. |
| Resource utilization | Assigned units divided by units available to that condition, per the existing rescue planner. |
| Invalidated original routes | Original assignments with an inaccessible/missing route edge, unavailable resource, or unsupported destination route. |
| Reassigned units | Units whose destination changes, including original units no longer assigned and new units entering the assignment set. |
| Unserved destinations | Eligible destinations not assigned by the optimizer; this can be large when inventory is small. |
| Assignment stability | Exact unit/destination pairs preserved by the separately optimized plan. |
| Critical dependency | Result of closing a road/bridge traversed by the original plan and rerunning the planner on the synthetic graph; not a field-verified infrastructure assessment. |

These are deterministic synthetic experiment statistics. Counterfactuals receive no probability weight; aggregate “robustness scores” are intentionally not presented.
