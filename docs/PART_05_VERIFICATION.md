# Part 5 verification

## Automated checks

Run backend tests with `.venv/Scripts/python.exe -m pytest -q --basetemp .pytest-tmp-part5` from `backend/`; a workspace-local pytest temp root is needed on some Windows installations where the default user temp folder denies access. Run `npm run typecheck`, `npm run lint`, `npm test -- --reporter=dot`, and `npm run build` from `frontend/`.

The suite covers corridor intersections, six explicit bridge segments, graph connectivity, graph-following route geometry, unsupported boat routing, manual closure exclusion, SQLite plan persistence, and stale-version rejection. Existing simulation and ML tests remain part of the full backend suite.

The emergence-only evaluation is run separately with `python -m app.ml.emergence_evaluation` from `backend/`. It replays only the unchanged held-out scenario IDs from the saved model metadata, filters out currently exposed buildings, and writes `backend/ml_artifacts/emergence_evaluation.json`. On the checked-in local artifacts it selected 3,650 examples (1,321 positive / 2,329 negative). The classifier scored precision 0.9478, recall 0.8933, F1 0.9197; the existing transparent heuristic scored 0.7910, 0.9425, 0.8601. This is synthetic-only analysis and does not establish real-world performance.

## Limitations

This is a synthetic decision-support demonstration. Access spurs connect point locations to a nearest road node within 90 m; sidewalks, building entrances, traffic, turn restrictions, road widths by vehicle, and flood depth along every continuous segment are not modeled. Road exposure is inherited from the existing per-corridor impact sampler and bridge deck status from its existing overtopping rule. Vehicle thresholds and speeds are assumptions, not emergency operating standards. Assignment search is exact for the current small inventory. Boat routing, alternate route ranking, drag-to-edit mission assignments, movement execution, and an emergence-only held-out ML report are not yet included.

The app was started locally, but browser automation was interrupted by the computer-use helper reporting concurrent user input and a minimized browser window; I stopped UI input rather than risk acting on stale browser state. FastAPI TestClient verified plan generation, manual-closure invalidation, reassignment, and approval; the frontend's component suite and production build also passed. CI runs after the branch is pushed; its result must be checked on GitHub before merge.
