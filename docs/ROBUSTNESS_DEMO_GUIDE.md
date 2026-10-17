# Demo Chapter: What if our plan fails?

1. Open a saved synthetic flood scenario and note its seed, tick, epoch, state version, and infrastructure revision.
2. Generate or select a current rescue proposal. Point out the actual displayed assignments and the commander-approval gate.
3. Open Decision Robustness and record the frozen available/reserved units and local model reliability.
4. Run the bounded conditions: rainfall escalation, one selected bridge/road closure, one ambulance unavailable, and an explicitly injected local-model outage.
5. Select the bridge-closure row. Compare “original routes still feasible” with the separate reoptimized assignment count and coverage denominator.
6. Inspect an invalidated original assignment and its saved route-level failure reason.
7. Inspect the dashed purple alternative route and amber/red hypothetical closure in the single CityScene canvas. Keep the “HYPOTHETICAL” label visible.
8. Compare critical infrastructure dependencies and any computed commander-review contingency. If the graph has no feasible alternative, state that directly.
9. Refresh the live Command Center. Confirm the scenario version and operational mission list did not change from the study.
10. Explain that actual response requires a fresh current proposal and explicit commander review/approval.

The release benchmark seed is `2026`, beginning at tick 12 after 12 deterministic flood steps with rainfall 300 mm/h, river stage 2.5 m, and drainage effectiveness 0. Reproduce it with `cd backend; .\.venv\Scripts\python.exe benchmark_robustness.py`. This stress setup is a fictional test, not a real-world forecast.
