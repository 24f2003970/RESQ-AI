# Team Workflow

## Roles for two developers

- **Developer A — backend, simulation, and ML:** owns domain schemas, seed generator, flood process, API/WebSocket, event persistence, risk training/evaluation, and algorithmic agents.
- **Developer B — frontend, Digital Twin, and UX:** owns React shell, dashboard screens, 3D rendering, controls, state visualization, replay interactions, and responsive/accessibility behavior.
- **Shared ownership:** API contract, end-to-end vertical slice, review, integration, offline rehearsal, demo narrative, and major architecture decisions.

These are initial ownership areas, not isolated silos. The frontend uses backend fixtures early; both developers review any cross-boundary change.

## Git conventions

- `main` stays runnable and is the demo branch.
- Branch names: `feat/<short-name>`, `fix/<short-name>`, `docs/<short-name>`, `chore/<short-name>`.
- Commit messages use Conventional Commits where practical: `feat:`, `fix:`, `docs:`, `test:`, `chore:`. Keep commits focused and descriptive.
- Open a pull request for changes to `main`; include purpose, screenshots for UI work, verification performed, assumptions, and follow-ups.
- The other developer reviews API/schema changes and the relevant domain owner reviews logic. At least one person besides the author approves before merge when time allows.
- Prefer squash merge for small feature branches; delete merged branches after preserving required evidence.
- Never commit secrets, raw or licensed datasets without review, local databases, caches, virtual environments, or model checkpoints. Store data provenance and reproducible generation scripts instead.

## Working cadence

- Agree one small deliverable and acceptance check per day.
- Keep the current API fixture/schema in the repository so both sides can develop independently.
- Integrate at least daily; avoid long-lived branches.
- When one side changes a field or state transition, update schema, fixture, UI/service, and docs in the same PR.
- Tag known-good demo checkpoints; keep a short recorded fallback path if the live scenario fails.

## Review checklist

1. Does the change preserve deterministic replay and state ownership?
2. Are units, validation bounds, provenance, and failure states explicit?
3. Is the interface displaying real backend/evaluation output rather than invented metrics?
4. Are route/assignment constraints and human approval respected?
5. Are tests or manual verification described? Were files/data accidentally included?
6. Does the application still start offline with the documented setup?

## Data, model, and licensing hygiene

Track the source URL, terms/license, retrieval date, version, attribution, checksum, transformations, and target semantics for every external dataset. Keep access credentials outside Git. Do not publish the repository or include an open-source license until the owner explicitly chooses to do so.

**License recommendation:** Apache License 2.0 is a reasonable starting point for a permissive software release because it requires retaining notices and includes an express contributor patent grant. MIT is a simpler alternative if the team prefers fewer conditions. This is a project recommendation, not legal advice; no `LICENSE` file is present and the repository stays private until the owner approves the publication and license choice. See [Apache-2.0 summary](https://choosealicense.com/licenses/apache-2.0/) and [license comparison](https://choosealicense.com/licenses/).
