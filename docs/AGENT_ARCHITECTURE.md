# Agent architecture

RESQ-AI implements six explicit local algorithmic agents in `backend/app/agents.py`. These are deterministic components, not LLM personas. They share a validated event and a committed scenario snapshot and execute in dependency order: Hazard Intelligence → Impact Assessment → Rescue Priority → Routing → Resource Allocation → Commander / Strategy.

Each stage persists an `agent_runs` row keyed uniquely by `(event_id, agent_name)`. The record includes event/correlation IDs, epoch/version/revision, start/end timestamps, duration, a SHA-256 input hash, snapshot reference, compact JSON outputs and numerical evidence, proposed action, explanation, status, attempt and error. Agent code reuses the existing physical simulator, local classifier, Part 5 priority formula, NetworkX routes, and SciPy optimizer rather than generating prose-based decisions.

The model has synthetic training labels and uncalibrated future-exposure scores. Model unavailability yields an explicitly degraded physical/rule assessment, with no fabricated prediction. A routing or stage failure remains visible in its run row and leaves downstream agents skipped; retry re-executes skipped dependencies. The commander may save only a proposal. PlanStore enforces state freshness, closure revision, one-unit/one-destination constraints, and current approved reservations in its database transaction.

The explorer obtains real rows through local versioned REST and displays status, event, timeline, coordination order, evidence, route deltas and review links. It polls; it does not trigger automatic intelligence itself. Scenario producers write durable trigger events, so the backend remains responsible for processing when the browser is absent.

See `EVENT_ORCHESTRATION.md`, `DECISION_TRACE_CONTRACT.md`, and `REPLANNING_POLICY.md` for persistence, event order and trigger details.
