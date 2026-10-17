# Five-minute Innotech presentation

See [`INNOTECH_5_MINUTE_PRESENTATION.md`](INNOTECH_5_MINUTE_PRESENTATION.md) for the timed full narration and trigger actions. This final cue sheet keeps the live sequence short and the scientific boundaries clear.

## 0:00–0:30 — The problem

“Flood response connects changing hazards, vulnerable places, finite resources, and road access. RESQ-AI is a local prototype that makes those modeled decisions visible and reviewable in one place.”

## 0:30–1:15 — The Digital Twin

“This fictional city is driven by a deterministic flood simulator. The backend's current exposure is distinct from any model estimate. The environment and all conditions are synthetic.”

## 1:15–2:00 — Local ML and agents

“A locally trained random forest estimates a synthetic future-exposure label. Reliability and support warnings show where evidence is limited. Six deterministic algorithmic agents record their decisions; they are not LLMs and cannot approve a response.”

## 2:00–3:15 — Human-controlled planning

“A graph router checks the modeled roads, closures, bridges, and unit constraints. The assignment solver compares the declared priority objective with a transparent nearest-feasible baseline. A commander reviews and approves a plan before simulated missions reserve and dispatch units.”

## 3:15–4:10 — Failure and replanning

“A closed required road blocks a mission. We show the last supported position and return no route when the graph has no safe supported path. After reopening, a fresh route proposal can be reviewed. We do not show a detour while the closure still makes the path infeasible.”

## 4:10–5:00 — Evidence and limits

“A separate all-roads-closed scenario correctly assigns zero units. Our ten-group study is a synthetic engineering comparison, and the model metrics are simulator-derived. RESQ-AI is not an operational forecast or certified emergency-response service.”

## Ninety-second version

Use the exact copy in [`INNOTECH_90_SECOND_PITCH.md`](INNOTECH_90_SECOND_PITCH.md). It covers product purpose, simulation, ML, deterministic agents, constrained route/assignment logic, explicit approval, and the synthetic-only limitation.

## Technical follow-up

For judge questions, use [`INNOTECH_JUDGE_QA.md`](INNOTECH_JUDGE_QA.md) and [`INNOTECH_TECHNICAL_DEEP_DIVE.md`](INNOTECH_TECHNICAL_DEEP_DIVE.md). Claims should match current evidence rather than rely on memory of an earlier demo.
