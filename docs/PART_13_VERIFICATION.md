# Part 13 Verification

## Deterministic benchmark

Command: `cd backend; .\.venv\Scripts\python.exe benchmark_robustness.py`

The benchmark uses seed `2026`, an extreme synthetic scenario, 300 mm/h rainfall, 2.5 m river stage, zero drainage effectiveness, 12 flood ticks, then 11 deterministic counterfactual conditions over a further three ticks. It records original-plan feasibility separately from reoptimization. The model was available for the captured local run. The benchmark output is generated from saved computations; timing is machine/runtime-specific.

Captured local run: 4 baseline assignments; full 11-condition study runtime **560.785 ms**; serialized completed-study payload **182,756 bytes**. Per-condition timings ranged from **33.795 ms to 69.373 ms**. All conditions returned the existing `optimal_linear_sum_assignment` status. The unchanged-condition row advances through the same three-tick horizon; one original assignment is invalid by then under the evolving synthetic flood. With every modeled road corridor closed, the planner still found 3 assignments through the existing unit/building access-spur assumptions; this exposes a known graph-model limitation and is not a claim that an operational route exists. One ambulance unavailable reduced assignments to 2; two units unavailable reduced them to 1. Results are synthetic and not likelihood-weighted.

## Regression coverage

`backend/tests/test_robustness.py` covers frozen/idempotent study storage; no operational scenario, plan, mission, or outbox mutation; authoritative environmental stepping and mass balance; bridge-span closure representation; resource removal; route closure invalidation versus safe reoptimized graph edges; unknown assets and mismatched frozen identities; model-unavailable fallback; API study persistence; and historical-study marking after a live change.

`frontend/src/test/robustness.test.tsx` covers frozen baseline submission, version/epoch/revision identities, result matrix rendering, explicit hypothetical labeling, and the commander-review-only contingency language.

## Release checks

## Final local verification (2026-10-17)

- Backend: **82 passed**, 1 upstream Starlette/httpx deprecation warning.
- Frontend: **37 passed** across 12 test files.
- ESLint: passed with 2 existing hook-dependency warnings in `RobustnessLab.tsx` and `RobustnessSummary.tsx`; no lint errors.
- TypeScript: passed (`tsc --noEmit`).
- OpenAPI contract generation: passed (`backend/export_contract.py` and `npm run generate-api`); generated API schema is committed and the synced scenario fixture was restored.
- Production build: passed. Vite reports large JavaScript chunks (main 759 kB and 3D scene 979 kB); this is a bundle-size warning, not a build failure.
- Part 10 demo preflight: all readiness checks passed with the local services running.
- Disposable Part 10 commander acceptance: **17/17 checks passed** in 8,183.576 ms.
- Browser visual inspection: completed at the verified local `/robustness` URL. Confirmed the frozen snapshot, hypothetical-only guardrail, bounded condition controls, and currently connected local service. No live plan or mission was altered during visual verification.
- GitHub Actions: pending publication of the final commit and PR; add run URL and job conclusions after hosted checks finish.

The captured benchmark is above and is synthetic only. Known graph access-spur limitation remains documented there.
