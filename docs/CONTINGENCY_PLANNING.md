# Contingency Planning

The contingency service reports differences between saved original assignments and the separately optimized condition plan. A suggestion includes the triggering condition, condition/study ID, unit and destination, route geometry, unit type/capacity, synthetic travel distance/time, coverage after reoptimization, and evidence from the original-plan feasibility check.

Suggestions are not action requests. They are not saved as rescue proposals, do not dispatch a unit, and cannot update an approved mission. The commander must return to the live workflow, refresh the scenario and infrastructure state, request a new proposal, inspect it, and approve it through the existing version-checked path.

If no changed feasible assignment is returned, the study displays that no supported changed alternative was produced. It does not fabricate a backup. This does not preclude a fresh live assessment after actual conditions change.

Old studies are labeled historical when scenario epoch/state version or infrastructure revision changes. A historical study is evidence for its recorded snapshot only and never authorizes live action.
