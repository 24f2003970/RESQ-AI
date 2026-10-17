# RESQ-AI Innotech submission kit

Submission-ready materials are gathered here; unknown registration details are explicitly left for the student team. Nothing has been submitted to an organizer or competition portal.

## Project details

- **Project title:** RESQ-AI — Synthetic Disaster Intelligence and Rescue Decision-Support Prototype
- **Short description:** An offline-first prototype that simulates flood exposure in a 3D fictional city, presents locally estimated future exposure and reliability warnings, coordinates six deterministic analysis agents, and lets a commander review route-aware simulated rescue plans.
- **Problem statement:** Flood response planning requires teams to reason about changing water exposure, vulnerable destinations, limited units, and routes that can close as conditions evolve.
- **Solution overview:** RESQ-AI joins a deterministic flood simulator, local synthetic ML model, durable algorithmic decision traces, connected route constraints, constrained unit assignment, explicit human approval, and a persisted simulated mission clock in a local command-center interface.
- **Key differentiators:** A visible simulation-to-recommendation chain; local reproducible computation; route/infrastructure constraints; explicit human approval; mission persistence and reroute review; support/uncertainty notices; and truthful unreachable outcomes.
- **Technology:** React, TypeScript, React Three Fiber, Three.js, FastAPI, Python, SQLite, scikit-learn, NetworkX, SciPy, Vitest, Pytest.
- **Repository:** https://github.com/24f2003970/RESQ-AI
- **Release candidate:** `RESQ-AI v1.0.0-rc-final` (candidate only; PR review required).

## Abstract

RESQ-AI is an offline-first engineering prototype for exploring flood-response decision support. A deterministic simulator updates water conditions in a fictional city shown through an interactive 3D Digital Twin. A locally trained random forest estimates a synthetic future-exposure label and reports calibration and training-support context. Six deterministic agents create an inspectable analysis trace, while a flood-aware road graph and constrained assignment method produce a reviewable proposal. A commander must approve a plan before simulated missions reserve units; dispatch, movement, blockage, route revision, arrival, completion, and return-to-service remain explicit actions. Isolated scenario and robustness studies examine alternative conditions without issuing operational commands. All geography, labels, and outcomes are synthetic; RESQ-AI is not a certified forecast or operational emergency-response service.

## Evidence and architecture

- [Architecture diagrams](RESQ_AI_ARCHITECTURE_OVERVIEW.md)
- [Scientific comparison and ML evaluation](SCIENTIFIC_EVALUATION.md)
- [Machine-readable ten-case evidence](evidence/part15/scientific_evaluation.csv)
- [Model reliability card](ML_RELIABILITY_MODEL_CARD.md)
- [Genuine screenshots and capture caveats](VISUAL_EVIDENCE_GALLERY.md)
- [Candidate limitations](FINAL_KNOWN_LIMITATIONS.md)

## Demonstration materials

- [Five-minute final pitch](INNOTECH_FINAL_PITCH.md)
- [Ninety-second pitch](INNOTECH_90_SECOND_PITCH.md)
- [Editable slide storyboard](INNOTECH_SLIDE_STORYBOARD.md)
- [Judge Q&A](INNOTECH_JUDGE_QA.md)
- [Local startup and recovery](LOCAL_DEMO_QUICKSTART.md), [Demo A/B rehearsal](FINAL_DEMO_REHEARSAL.md)

## Contributors and acknowledgments

- Student team member 1: **[team member name to be completed by the team]**.
- Student team member 2: **[team member name to be completed by the team]**.
- Institution, department, mentor, registration ID, and acknowledgments: **[complete only with verified details]**.

The repository history and user-provided project context describe a two-student collaboration, but verified names and institutional submission details are not present in this handoff. No awards, affiliations, or external contributions are claimed.

## Submission checklist

- [ ] Confirm team names, institution, department, mentor and event-specific registration details.
- [ ] Confirm competition rules allow synthetic prototype evidence and local simulation demonstrations.
- [ ] Follow `FINAL_RELEASE_CHECKLIST.md`; review pending viewport/accessibility items.
- [ ] Rehearse Demo A and Demo B from fresh disposable scenarios.
- [ ] Confirm current repository commit and PR review state with the team.
- [ ] Verify any slide deck or attachments required by the official event portal.
- [ ] Submit manually through the official Innotech process; no submission has been made by this repository workflow.
