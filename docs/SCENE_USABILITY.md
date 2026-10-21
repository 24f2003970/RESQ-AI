# 3D usability and workflow verification

This change extends the navigation simplification on the same local branch. It does not add a new implementation phase or replace the Digital Twin.

## Exploration

- Camera controls now sit outside the canvas, with visible names for city overview, zoom, selected-building focus and building inventory. Lighting and camera destinations have labelled selectors. Destinations that need flood water, a bridge or a selected mission are disabled when unavailable.
- The accessible inventory supports search by building name, identity, use and district, plus a current-water filter. Depths and water-reach labels use the current scenario impact records; missing physical data is explicitly unavailable.
- A selection summary beside the scene distinguishes current physical water from a supported future ML estimate and links to the existing inspector. The inspector no longer labels every building as Baseline; it reads current physical depth even when ML is unavailable.
- Low graphics has an explicit On/Off label and explanation. Its preference is retained in browser storage when storage is available. It still only changes rendering detail, shadows and pixel ratio.
- The expanded legend explains numerical water-depth bands, separate future exposure estimates, proposed/ready/active/blocked routes and hypothetical overlays.
- Building camera focus includes authoritative ground elevation. The flood camera uses scenario grid coordinates rather than hard-coded grid origins. Mission route sampling and authoritative progress are unchanged.

## Verification

Local verification before PR delivery: frontend tests passed: **58 tests across 15 files**. TypeScript, ESLint and production build passed. Existing scene chunk-size and THREE.Clock deprecation warnings remain; no frame-rate improvement is claimed.

Existing disposable acceptance workflows passed: **17/17 Part 10 checks** and **14/14 RC1 checks**. These exercise actual local API services, explicit simulated commander actions, route progression, safe rerouting, mission completion/resource return, persistence and honest all-roads-closed refusal. They use temporary SQLite stores, preserving the normal preview database and model artifacts. They are API acceptance evidence, not a claim that the full mission sequence was manually performed in a browser.

The browser review covers searchable inventory, selection details, labelled controls, graphics preferences, layers/legend and responsive presentation. Review screenshots remain local deliverables. This focused review does not close every historical release accessibility/GPU/clean-machine gate. The PR delivery record reports publication status, the exact source commit and hosted check results separately. No merge, release tag or deployment is part of this change.
