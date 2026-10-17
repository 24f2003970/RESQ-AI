# Part 15 implementation

Part 15 packages the existing RESQ-AI prototype as a reproducible engineering showcase. It adds a deterministic local evaluation runner and machine-readable reports, an editable reliability plot, a linked research/presentation set, a curated set of genuine local-browser captures, and a portfolio README entry point. It does not change simulation, routing, ML, agent, approval, or mission behavior.

## Evaluation runner

`backend/run_part15_evaluation.py` evaluates ten deterministic scenario groups. Each group uses a disposable SQLite store, a fixed seed, six flood steps, and one final scenario-level observation. The cases cover mild forcing, moderate and severe flood conditions, increased river stage, reduced drainage, an important-road closure, bridge disruption, limited inventory, an explicit model-unavailable fallback, and a fully closed road graph. Repeated ticks within a group are correlated simulator steps, not independent samples.

Each case evaluates the conventional nearest-resource baseline and the existing priority-weighted assignment with compatible scenario state, eligible destinations, inventory, graph and route constraints. The output records coverage, objective, unreachable count, route distance, estimated synthetic travel time, resource use, route and assignment timing, and solver status. The runner writes JSON, CSV and Markdown beneath `docs/evidence/part15/`. It sets a unique temporary SQLite path before importing app services; it does not connect to or mutate the operational database.

Reproduce from the repository root:

```powershell
.\backend\.venv\Scripts\python.exe .\backend\run_part15_evaluation.py
.\backend\.venv\Scripts\python.exe -m pytest .\backend\tests\test_part15_evaluation.py --basetemp=.pytest-tmp-part15
```

The evaluation is intentionally small enough for an ordinary laptop. Ten scenario groups support a bounded engineering comparison; they do not establish statistical performance over real disasters.

## Reliability evidence

`backend/plot_part15_reliability.py` creates `docs/evidence/part15/calibration_reliability.svg` from the saved Part 12 reliability bins. The two panels distinguish nested development adoption evidence from the untouched synthetic test split. Both axes identify predicted probability and observed frequency, and points carry bin counts. The plot is a derived analytical figure, not a browser screenshot. The model artifact was not retrained or replaced.

The saved evidence reports 72 synthetic scenario groups (42 train, 15 validation, 15 untouched test) and a six-step, five-minute-tick prediction horizon. Calibration was adopted using the nested grouped development gate. On development, raw versus Platt Brier score was 0.032189 versus 0.029793 and log loss was 0.113304 versus 0.102349. On the untouched synthetic test split, raw versus Platt Brier score was 0.030526 versus 0.027917 and log loss was 0.106666 versus 0.094190. These metrics describe synthetic labels only.

## Documentation and evidence

The companion documents link the scientific protocol, architecture boundaries, benchmark reproduction, five-minute presentation, short and extended pitches, slide storyboard, judge Q&A, recovery guidance, portfolio case study, visual gallery, and final visual QA. Captures are real images from the locally launched app with a disposable database. They document observed states only; the gallery calls out lifecycle states that were not captured in this Part 15 browser session.

No application behavior or public API was changed. No live-data integration, external model API, real emergency dispatch, real-world calibration claim, or Part 16 work is included.
