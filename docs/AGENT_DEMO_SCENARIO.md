# Part 6 demo scenario

## Setup

Follow the root README local setup and start the backend plus frontend. The default fictional Riverside seed is 2026. Open Scenario Lab, create an **Extreme** scenario, set rainfall to **300 mm/h**, river stage to **5 m**, drainage effectiveness to **0**, and advance the simulation. A reproducible backend benchmark can run the exact 120-step scenario with:

```powershell
cd backend
.\.venv\Scripts\python.exe benchmark_agents.py
```

The script prints the measured local-model status, impact counts, event and agent timing fields, proposal ID and each agent status. The 120-step operation is for a benchmark; for a live demo, advance in smaller increments so the Explorer and Command Center remain visible.

## Live narrative

1. Show measured water depth and the separate synthetic 30-minute exposure layer.
2. Open AI Decision Explorer. Select the simulation advance event and follow the six persisted agents in order.
3. Inspect numerical exposure, road/bridge changes, priority deltas, unreachable locations, routes and the Part 5 baseline comparison.
4. Return to Command Center. The actual current proposal is loaded into Rescue Planning and its backend-computed graph polylines are shown in the 3D city.
5. Choose an open route-relevant road and close it. The route graph removes that edge. `test_manual_closure_changes_a_real_route_and_supersedes_old_proposal` demonstrates the `unit-1` to `building-0-0-0` route switching away from `road-ew-1` under seed 2026 when that edge is available in the selected route.
6. Inspect the new infrastructure revision and trace; verify the changed route pair and updated assignment.
7. Approve or reject the replacement proposal explicitly. The Commander agent never approves it.

The automated closure test validates actual route-edge change rather than relying on the wording of a notification. If a selected city/flood configuration already blocks the road or leaves no alternate route, choose a route shown in the live trace instead of asserting a replan that did not occur.
