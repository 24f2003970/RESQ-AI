# Judge questions and accurate answers

### Is this an LLM or a hosted AI service?

No. Inference uses a model trained locally on generated scenarios. The six agents are deterministic algorithmic components. Runtime inference and coordination do not call a hosted API.

### How was the model trained and evaluated?

The dataset is generated from the project's synthetic flood simulator. Scenarios are grouped so held-out scenario groups are excluded from fitting and model selection. The Model Intelligence Lab shows the saved test metrics and rule baseline from the shipped evaluation artifact. This measures performance on generated data only; it does not validate real flood forecasts.

### What does the 3D city represent?

It renders backend city geometry and current scenario outputs. Flood depth and building exposure are simulation results. The predicted layer is a separate local-model estimate for a synthetic future horizon.

### What makes the rescue plan feasible?

The proposal uses the current route graph, open infrastructure, unit capacities, destination uniqueness and resource reservations. Unreachable destinations are reported. A plan has scenario and infrastructure versions and remains a proposal until a commander decides.

### What is the baseline comparison?

It compares the optimizer with the project's documented conventional allocation baseline using the same scenario inputs and constraints. It is an algorithmic comparison, not evidence of superiority over a real response organization.

### What happens when a road closes?

The backend records the closure and the dispatched unit's authoritative route progress. Remaining route feasibility is recalculated against the open graph. A replacement route requires a fresh explicit commander approval; if no supported safe path exists, the unit stays blocked.

### Does mission arrival mean people were rescued?

No. It means only that the simulated unit reached its destination. Completion is a separate explicit state transition. Neither state verifies an evacuation or counts lives saved.

### Can it be used in a real emergency?

No. The city, population, labels, process model and operations are synthetic. The flood engine and model are not validated for operational use, and prioritization weights are not clinically validated triage criteria.

### What if the laptop cannot render the city?

Use the Low graphics setting. If the 3D scene still fails, Judge Mode shows a backend-derived exposure table and links to the scenario, model and agent records. The UI is not a substitute for a verified map in an actual incident.

### How is offline operation verified?

Source and configuration review plus loopback preflight verify local URLs and application endpoints. This is not a packet capture or a claim about every host process on the laptop. First-time package installation still requires a package registry connection.
