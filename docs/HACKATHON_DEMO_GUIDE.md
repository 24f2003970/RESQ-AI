# RESQ-AI Guided Hackathon Demo

## Prepare

Start the local backend and frontend as described in the README. Keep the self-trained model artifact in `backend/ml_artifacts`; the demo deliberately stops at the model stage if local inference is unavailable. No hosted AI or map service is required.

Open **Guided Demo** from the app navigation and choose **Initialize demo scenario**. This creates a separate paused scenario named for the guided demo with seed `2026`, preset `mild`. The existing scenario remains untouched.

## Ten-stage walkthrough

1. **Initial City:** introduce the 3D city and seeded buildings, hospital, shelter, roads and response inventory.
2. **Flood Event:** apply 90 mm/h rain, river stage 1.4 m and 20% drainage, then advance 12 fixed ticks (one simulated hour). This seed/forcing combination produces measured building and road exposure while retaining route segments for the closure demo. Point to backend physical exposure counts.
3. **AI Risk Intelligence:** run the local trained model. Explain that current physical exposure and synthetic, uncalibrated future-risk labels are separate measurements.
4. **Agent Coordination:** queue/observe an actual assessment event and its ordered six-agent trace. Wait for a completed or degraded persisted trace; timeouts never claim completion.
5. **Rescue Recommendation:** inspect the actual proposal, assigned units, destinations and graph route segments. Approval is still pending.
6. **Infrastructure Disruption:** close the first road segment of a current assigned mission through the backend. The selected road must be present on that saved route.
7. **Autonomous Replanning:** wait for the closure event and fresh proposal. The UI verifies that the same unit/destination route changed or became unreachable; if it did not, it says so and stops the claim.
8. **Human Decision:** explicitly approve or reject the proposal. Nothing is auto-approved.
9. **Impact Comparison:** run a saved, zero-additional-tick A/B resource experiment using the same current snapshot and closure, with four versus two ground units total. Compare actual baseline and optimized assignment outputs.
10. **Explainability:** open the persisted event trace in Decision Explorer, including the closure trigger, agent evidence and proposal relationship.

## Reset and repeat

Reset returns the demo scenario to its seeded initial state and retains earlier traces as history. If the scenario has approved plans, the UI first warns that reset starts a new epoch and makes approvals historical. Reservations are scoped to the old epoch. Part 8 supports explicit simulated completion and commander return-to-service; resource release is never automatic.

For an automated, actual-ML acceptance run from `backend/`, execute `.\.venv\Scripts\python.exe demo_acceptance.py`. It prints a JSON PASS/FAIL report with scenario, event and plan IDs, physical exposure, route before/after, infrastructure revision, decision trace and resource conflict evidence.

## Honest limitations

The city, model training data and labels, flood process, route speeds, occupancy, resource capacities and decisions are synthetic. Model scores are uncalibrated. A closure may yield an explicit infeasibility or unchanged route in another setup; do not describe an unchanged route as a successful replan. This is an educational decision-support prototype, not an emergency dispatch tool.
