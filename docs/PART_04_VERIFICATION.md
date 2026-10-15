# Part 4 verification record

## Branch and base

Part 4 branch: `feature/part-04-ml-intelligence`, created from `origin/main` after confirming Part 3 merge commit `ccd3c2b93535f7123310f316ad34e4d502088b0e`.

## Automated checks

Backend pytest: 25 passed using a workspace-local pytest temp root, including fresh generated-data training, artifact-save, and missing-artifact behavior checks. Frontend Vitest: 9 passed. TypeScript typecheck and ESLint passed. Production build passed; the separately split CityScene chunk remains ~963 kB and still triggers Vite's 500 kB advisory. Python `pip check` reported no broken requirements. The local model info/evaluation endpoints returned the trained artifact, and active-scenario inference returned 72 state-versioned building predictions.

## Browser review

The isolated deterministic demo run used scenario `scenario-a8de182f27f3`, seed 2026, rainfall 100 mm/h, stage 0.8 m, drainage 0.4, and 30 simulated minutes. Backend result: 0.311 m maximum land depth, 18 affected buildings, 6 exposed roads, and 6 closed bridges. These are measured from the scenario store. Desktop browser review and screenshot were attempted, but the computer-use helper blocked interaction because it could not verify the current Chrome URL; no screenshot is claimed.

## Demo scenario

Run `python -m app.ml.demo_scenario` from `backend/`. Use seed 2026, rainfall 100 mm/h, river stage 0.8 m, drainage effectiveness 0.4, and advance six fixed five-minute ticks (30 simulated minutes). A measured run produced 18 affected buildings, 0.311 m max land depth, 6 exposed roads, and 6 closed bridges. These are synthetic conditions and are not calibrated to a real location.
