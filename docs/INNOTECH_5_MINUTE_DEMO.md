# Innotech five-minute demo

Use the local launcher and preflight first. Set low graphics before presenting if the laptop is underpowered. The sequence uses the existing Guided Demo and its real API responses; never skip a required human decision.

| Time | Presenter action | Explain |
|---|---|---|
| 0:00–0:30 | Enter Judge Mode and show the default city | This is a fictional city rendered from backend geometry and local scenario state. |
| 0:30–1:10 | Open Guided Demo and initialize the seed-2026 scenario | It creates an isolated operational scenario and does not overwrite other scenarios. |
| 1:10–1:50 | Apply the severe rainfall preset and advance 12 simulation ticks | The backend computes flood depth, exposed buildings and exposed roads. State these as simulated physical outputs. |
| 1:50–2:15 | Run local ML inference | Compare current physical exposure with predicted future exposure; scores use synthetic labels and are not real-world forecasts. |
| 2:15–2:50 | Run the six-agent assessment and inspect its persisted trace | These are deterministic algorithmic components; show event/version, evidence and any degraded status. |
| 2:50–3:25 | Load and inspect the rescue proposal | Explain the assigned unit, route constraints, solver status and conventional baseline. It is still a proposal. |
| 3:25–4:05 | Close a route-relevant road, wait for the fresh replan, then explicitly approve or reject | Show the disruption and the new persisted result. If unreachable, explain that the system preserves that constraint. |
| 4:05–4:35 | Open the optional mission chapter; dispatch and advance mission time if ready | Position changes only with backend mission time. A blocked state requires a reviewed route revision. |
| 4:35–5:00 | Show arrival/completion distinction, saved A/B evidence and Judge Mode | Arrival does not complete a mission. No human action is automated; no real rescue result is claimed. |

If the run takes longer, omit the optional mission chapter and use the saved mission records in Judge Mode. Do not claim a result that did not appear in the UI.
