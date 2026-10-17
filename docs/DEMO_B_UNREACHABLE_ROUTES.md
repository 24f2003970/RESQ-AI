# Demo B — correct refusal when no ground route is supported

Demo B creates a separate scenario (seed `2026`, rainfall `30 mm/h`, river stage `0.6 m`, drainage `0.2`, six flood ticks). The flood simulation still produces **10 affected buildings**. The acceptance runner then closes all **10 modeled road corridors** using the normal closure API.

The resulting rescue proposal has **0 assignments**, creates **0 mission records**, and records **12 unreachable destinations**. Its explanation says no compatible ground unit has a connected traversable route under the synthetic graph assumptions, and names closures, flooding, bridge status and unit depth limits as constraints.

This is expected behavior. The UI presents a short no-supported-route summary and reveals a few concrete reasons on demand instead of dumping every building identifier into the page. Judge Mode and the Robustness Lab remain analytical/read-only; neither creates an operational mission. This synthetic graph is not surveyed connectivity, and an open simulated route is not a field-safety claim.

Reproduce both Demo A and Demo B with `backend/.venv/Scripts/python.exe backend/demo_acceptance_rc1.py`; all writes use a temporary SQLite database.
