# Judge Mode guide

## Start and exit

1. Start the app using [Local Demo Quickstart](LOCAL_DEMO_QUICKSTART.md) and confirm the preflight passes.
2. Use **Judge Mode** in the top bar. The live presentation view uses the same scenario snapshot as Command Center.
3. Use **Exit Judge Mode** to return to Command Center. No scenario is created or reset by entering the mode.

## Presenter flow

- Introduce the synthetic city and its current scenario version.
- Explain the current simulated flood depth and physically exposed building count.
- If the model prediction matches the displayed scenario version and tick, explain the separate future-exposure count and its synthetic horizon. If it is stale or unavailable, say so and open Model Intelligence Lab.
- Read the current persisted agent status and use **View decision evidence** to inspect its event trace.
- If a current proposal exists, explain its routes, coverage and solver status. For `proposed`, use **Open commander review** and make the human decision explicitly in Command Center.
- Distinguish mission `arrived` from `completed`; completion remains a commander action. A unit is restored only through the explicit return-to-service action.
- Use Scenario Lab and Guided Demo for mutations and the full repeatable story.

## Controls and caveats

Low graphics starts enabled and can be changed with the labeled checkbox. Predicted-risk overlay is disabled unless the prediction belongs to the current scenario state. If the 3D scene fails, use the exposed-building evidence table and the links to detailed workspaces. All city data, model labels, population and outcomes are synthetic; the system is not an emergency-response service.
