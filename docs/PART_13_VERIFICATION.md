# Part 13 Verification

## Deterministic benchmark

Command: `cd backend; .\.venv\Scripts\python.exe benchmark_robustness.py`

The benchmark uses seed `2026`, an extreme synthetic scenario, 300 mm/h rainfall, 2.5 m river stage, zero drainage effectiveness, 12 flood ticks, then 11 deterministic counterfactual conditions over a further three ticks. It records original-plan feasibility separately from reoptimization. The model was available for the captured local run. The benchmark output is generated from saved computations; timing is machine/runtime-specific.

Part 13.1 final rerun after removing isolated-node/access-spur-only paths: 2 baseline assignments; full 11-condition study runtime **348.700 ms**; serialized completed-study payload **264,819 bytes**. Per-condition timings ranged from **22.515 ms to 50.797 ms**. All conditions returned `optimal_linear_sum_assignment` (the assignment solver completed; zero assignments is a valid result when no route is supported). At the three-tick extreme-flood horizon, all 2 original routes were unsupported and all 72 destinations were unserved in every condition; the baseline plan was still generated at tick 12, and this stricter result reflects subsequent synthetic depth limits and frozen resource availability. With every modeled road corridor closed, there were **0** reoptimized assignments, replacing the prior invalid 3 access-spur-only results. This is synthetic graph evidence, not an operational safety determination.

## Regression coverage

`backend/tests/test_robustness.py` covers frozen/idempotent study storage including manual closures in study identity; closure union across baseline, environmental, resource, bridge and road cases; no operational closure mutation; route closure invalidation versus supported reoptimized graph edges; unknown assets and mismatched frozen identities; model-unavailable fallback; API study persistence; and historical-study marking after a live infrastructure change. `backend/tests/test_rescue.py` covers all-roads-closed zero assignment, isolated-node rejection, explicit co-located-on-network behavior, valid building access on an open road, genuine detours, bridge closures, and unit-specific flood depth limits. The full backend suite also exercises mission route behavior.

`frontend/src/test/robustness.test.tsx` covers frozen baseline submission, version/epoch/revision identities, result matrix rendering, explicit hypothetical labeling, commander-review-only contingencies, immediate hiding on scenario switch, and ignoring delayed responses from a previously selected scenario.

## Release checks

## Final local verification (2026-10-17)

- Backend: **89 passed**, 1 upstream Starlette/httpx deprecation warning.
- Frontend: **39 passed** across 12 test files.
- ESLint: passed with no warnings or errors.
- TypeScript: passed (`tsc --noEmit`).
- OpenAPI contract generation: passed (`backend/export_contract.py` and `npm run generate-api`); generated API schema is committed and the synced scenario fixture was restored.
- Production build: passed. Vite reports large JavaScript chunks (main 759 kB and 3D scene 979 kB); this is a bundle-size warning, not a build failure.
- Part 10 demo preflight: all readiness checks passed with the local services running.
- Disposable Part 10 commander acceptance: **17/17 checks passed** in **8,153.651 ms**.
- Browser visual walkthrough: completed at the verified local `/robustness` URL. Confirmed the frozen snapshot, hypothetical-only controls, scenario identity, completed result matrix, synthetic-graph wording, live-baseline-only water label, and low-graphics scene. The generated study stayed analytical and did not change live plans or missions.
- Hosted GitHub Actions for code commit `7ec1b0c91c555deca77617d7f7445ee3e98e6744`: [run 39018139565](https://github.com/24f2003970/RESQ-AI/actions/runs/39018139565) — backend **success**, frontend **success**. The verification-record follow-up `a2b100abd176179e4f80e694c7f4847db1c705b4` also passed both jobs in [run 39018257667](https://github.com/24f2003970/RESQ-AI/actions/runs/39018257667).

The captured benchmark is above and is synthetic only. Ordinary building access spurs remain supported only when connected to a traversable road network. A route supported by this model does not establish surveyed connectivity or field safety.
