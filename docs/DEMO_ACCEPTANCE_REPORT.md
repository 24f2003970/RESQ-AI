# Signature Demo Acceptance Report

## Reproduction

Run `cd backend; .\.venv\Scripts\python.exe demo_acceptance.py`. The script uses a temporary operational SQLite database, the installed local model artifact and the real flood engine, `AgentOrchestrator`, `PlanStore` and routing/assignment services. It does not fake model predictions or a changed route.

## Latest local acceptance run

**PASS**, seed `2026`, mild scenario, parameters `rainfall=90 mm/h`, `river=1.4 m`, `drainage=0.2`, 12 ticks (60 simulated minutes).

- Flood step runtime: **119.0 ms** for the 12-tick operation.
- Physical result: **59 affected buildings**, **8 exposed roads**.
- Local model: version `1.0.0`; **70 predicted future-exposed** building labels. These are uncalibrated synthetic-model outputs, separate from the 59 physical exposures.
- Flood event `2cae6e340fdb44bf91cdedb84c0cb934`: six-agent trace completed; initial proposal `7cd098df-e9c8-4bbc-8168-998362519a39` assigned `unit-1 → building-0-1-0` over `road-ew-1`.
- Closure event `756fdc37810049b497bb688a7e7f87e8`: road `road-ew-1` closed; infrastructure revision moved `0 → 1`; initial proposal became `superseded`; fresh proposal `46405784-1789-406f-bc1a-36da7a7fefe6` remained proposed; the same unit/destination became unreachable.
- Human approval event `ed6ff4be65ac483da752f3d31109f308` completed with a persisted trace. The approved proposal reserved `unit-1`, `unit-2`, `unit-4`, `unit-5`; the subsequent strategy assigned no overlapping units (it found no remaining feasible missions).
- Total script runtime: **1.41 seconds**.

The script generates new IDs on each run; the values above identify this particular run. The result establishes that the selected seed and forcing reliably produce a real route-relevant closure response on the local installed artifacts, not that every arbitrary scenario will have a feasible replacement.

## Actual A/B and baseline benchmark

Separate local run from the same seed and severe physical snapshot: seed `2026`, 300 mm/h rainfall, 5 m river stage, zero drainage, six ticks (30 simulated minutes), then zero additional ticks for A/B. Variant A used two ambulances and two ground teams; B used one of each. Both variants retained the identical six-tick physical state: maximum depth **2.2294 m**, **72/72** buildings affected, **10** exposed roads, **6** closed bridges, **58** destinations unreachable. ML was available as version `1.0.0` and uncalibrated.

| Variant / method | Destinations | Weighted coverage (pts) | Occupants | Distance (m) | Travel-time sum (min) | Max arrival (min) | Utilization | Objective |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A conventional | 4 | 16.20 | 16 | 695.6 | 4.8 | 1.9 | 100% | 15.48 |
| A optimized | 4 | 29.40 | 16 | 480.7 | 3.9 | 1.5 | 100% | 28.82 |
| B conventional | 2 | 7.40 | 8 | 451.8 | 2.8 | 2.1 | 100% | 6.98 |
| B optimized | 2 | 15.93 | 8 | 340.9 | 2.4 | 1.7 | 100% | 15.57 |

Within A, optimized versus baseline improved weighted coverage by **13.20 points (+81.48%)**, while reducing distance by **214.9 m (−30.89%)**, travel-time sum by **0.9 min (−18.75%)**, and maximum arrival by **0.4 min (−21.05%)**. Within B it improved coverage by **8.53 points (+115.27%)**, reduced distance by **110.9 m (−24.55%)**, travel-time sum by **0.4 min (−14.29%)**, and maximum arrival by **0.4 min (−19.05%)**. Percentages use baseline as denominator.

With fewer resources, optimized Variant B versus optimized A covered **2 fewer destinations (−50%)**, targeted **8 fewer occupants (−50%)**, and weighted coverage fell **13.47 points (−45.82%)**. Total distance/time also fell because fewer missions were assigned; this is not an improvement in coverage. In a separate diagnostic comparison, the B maximum arrival can worsen despite a lower time sum, demonstrating why both values are reported.

This benchmark is synthetic and scenario-specific. It is not a general claim that optimization always wins. Timings are one local Windows run: whole experiment **357.4 ms**, serialized payload **111,294 bytes**; Variant A routing **32.9 ms**, assignment **0.12 ms**; Variant B routing **18.8 ms**, assignment **0.09 ms**. Warm/cold model and machine variance apply.
