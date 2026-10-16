# Part 11 verification

## Automated checks

Verified on 2026-10-16 from the Part 10 merge base using the repository Python 3.12 environment and installed frontend dependencies:

```powershell
Push-Location backend
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-temp-part11
Pop-Location
Push-Location frontend
npm test -- --reporter=dot
npm run lint
npm run typecheck
npm run generate-api
npm run build
Pop-Location
.\scripts\demo-preflight.ps1
.\backend\.venv\Scripts\python.exe .\backend\demo_acceptance_part10.py --test-commander-actions
```

- Backend pytest: **67 passed**, one existing Starlette/httpx deprecation warning.
- Frontend Vitest: **33 passed across 11 files**.
- ESLint: passed.
- TypeScript checking: passed, including after API contract generation.
- Backend OpenAPI export and frontend TypeScript contract generation: passed. The backend generator refreshes random fixture event IDs; those unrelated fixture changes were restored.
- Production build: passed. Vite reports the lazy CityScene chunk at 978.25 kB minified / 261.82 kB gzip and the initial app JS at 725.11 kB / 213.93 kB gzip; both exceed Vite's 500 kB chunk warning threshold.
- Part 10 read-only preflight: **24/24 passed**.
- Part 10 disposable end-to-end acceptance: **PASS in 8,408.7 ms**. It verified 12 flood ticks, 59 exposed buildings, 8 exposed roads, 72 local predictions, six-agent trace persistence, four computed assignments, approval/reservation and pending-event recovery across restart, blocked route handling, arrival, explicit completion/return-to-service, replay, and isolated A/B persistence.

The explicit test flag is only for the disposable acceptance workflow; it is not a UI approval mechanism. The preflight is read-only. Build results do not substitute for browser inspection.

## Judge Mode cases

Vitest checks that the entry route receives the same scenario object as the normal app, exiting returns to Command Center with the same scenario ID, physical and predicted metrics remain separately labeled, prediction counts are hidden for stale simulation or model versions, stale infrastructure suppresses proposal claims, commander status follows persisted decisions, evidence links include the persisted trace event, low-graphics remains keyboard operable, API failures surface an alert, and backend exposure evidence remains available if the 3D scene fails.

## Visual status

The Part 10 launcher reported the local URL and the preflight passed. The computer-use helper then stopped before selecting a browser because it could not determine the current browser URL on Windows with sufficient confidence to enforce policy. Per the visual verification instructions, the browser workflow was stopped. No browser screenshot, viewport inspection, Judge Mode walkthrough, GPU setting, or FPS result is claimed. See [Visual Acceptance Part 11](VISUAL_ACCEPTANCE_PART_11.md).
