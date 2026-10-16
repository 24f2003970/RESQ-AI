# End-to-End Acceptance

From the repository root, explicitly authorize the synthetic test commander actions:

```powershell
.\backend\.venv\Scripts\python.exe .\backend\demo_acceptance_part10.py --test-commander-actions
```

Without that flag, the runner exits before creating a database or taking any action. With it, the runner sets `RESQ_DB_PATH` to a temporary folder and calls the production FastAPI endpoints using an in-process `TestClient`. It does not make internet requests or use the user's normal scenario DB. The temporary database is removed when the process exits.

It verifies health/city, deterministic seed and flood exposure, local model/dataset/evaluation and inference, six-agent event trace, computed rescue plan, explicit approval, mission creation/reservations, a fresh-app restart, test dispatch, an infrastructure closure, blocked state, reviewed route replacement or explicit infeasibility and recovery, authoritative mission clock to arrival, explicit completion, return-to-service, read-only replay, and isolated A/B variants. Every successful stage has an assertion against returned persisted state.

Outputs:

- `artifacts/part10-acceptance/acceptance-report.json`
- `artifacts/part10-acceptance/acceptance-report.md`

The report contains scenario and mission IDs, checks and timings. A timing with one sample is a measured run, not a stable performance claim. The acceptance test's simulated commander decision applies only to the synthetic temporary scenario.
