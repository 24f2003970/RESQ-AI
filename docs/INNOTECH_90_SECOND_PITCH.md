# RESQ-AI · 90-second pitch

**0:00–0:15 — The challenge**
During a flood, commanders need to understand what is affected, which roads are usable, and how a small number of response units can reach priority locations. A static map cannot show how those decisions change when water rises or a route closes.

**0:15–0:34 — The product**
RESQ-AI is an offline-first, fictional disaster decision-support prototype. Its Digital Twin displays a deterministic flood simulation. A locally trained model estimates future exposure, with visible support warnings. Six event-driven algorithmic agents turn those inputs into a reviewable rescue recommendation.

**0:34–0:58 — The response loop**
The router uses a synthetic flood-aware road graph. A SciPy assignment solver compares its priority-weighted plan against a transparent greedy baseline. A human must approve the plan, explicitly dispatch a unit, and review any route revision. Mission movement follows persisted backend progress.

**0:58–1:15 — Evidence**
Our grouped ML evaluation keeps scenario histories together, then evaluates on 15 untouched synthetic scenario groups. A separate ten-case routing study reproduces lower and severe flooding, closures, a bridge disruption, limited resources and missing model evidence. When every road is closed, it returns zero assignments.

**1:15–1:30 — Honest boundary**
All cities, people, labels, roads and outcomes are synthetic. This is a research and engineering prototype, not a certified emergency product. RESQ-AI demonstrates how simulation, uncertainty, route feasibility and human control can fit into one inspectable decision workflow.

**Suggested visual:** verified Command Center, then the reliability plot, then the all-roads-closed result. Sources: [Scientific evaluation](SCIENTIFIC_EVALUATION.md), [architecture](RESQ_AI_ARCHITECTURE_OVERVIEW.md), [gallery status](VISUAL_EVIDENCE_GALLERY.md).
