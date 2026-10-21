# Navigation and rescue workflow

The main navigation now follows four common tasks: Overview, Flood simulation, Rescue operations and Guided demo. Digital Twin Studio, agent decisions, Model Intelligence Lab and Decision Robustness remain available in an expandable Advanced tools menu. Existing routes remain valid.

A three-step guide links flood setup to plan review and mission tracking. `/response` displays existing planning controls; `/response?view=missions` displays existing mission controls. Both components stay mounted within the workspace so changing steps retains drafts, selection and polling. Visibility changes do not issue approval, dispatch, completion or resource-return commands. The existing shared scenario remains authoritative. The original `/?review=latest` review entry remains usable; agent and Judge Mode review links now target `/response`.

The overview keeps city state, the 3D scene and inspection available while placing response controls in their dedicated workspace. Agent and robustness evidence, scenario comparison, and export options are disclosed on demand. Mobile navigation retains text labels; response controls appear before the scene on narrow screens.

Backend APIs, saved model artifacts, routes, mission state transitions, freshness checks, replay and analytical isolation are unchanged. No release manifest is generated for these uncommitted changes.

Validation: 54 frontend tests across 14 files passed, including navigation without mutation commands, direct mission entry, legacy review links, history navigation and existing mission/planning contracts. Lazy route integration tests allow longer waits for module loading on busy local machines. Production build and lint passed. Connected browser checks covered the desktop overview and response steps at 1440 x 900, and mobile navigation/layout at 390 x 844. This is a focused navigation review; it does not complete the historical full release QA matrix.
