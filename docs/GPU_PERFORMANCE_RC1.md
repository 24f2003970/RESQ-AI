# RC1 graphics performance

## Instrumentation and build profile

The pre-RC1 build measured the primary JavaScript chunk at 761.99 kB minified / 223.60 kB gzip and the already-lazy CityScene chunk at 979.30 kB / 262.11 kB. The Part 14.1 production build measured the initial JavaScript at 636.95 kB / 190.40 kB, saving **125.04 kB minified / 33.20 kB gzip**. CityScene is 980.87 kB / 262.75 kB. The 500 kB warning remains; it was not raised. CityScene remains lazy-loaded until the 3D workspace is selected.

The development-only `?perf=1` probe samples React Three Fiber frame deltas and Three.js `renderer.info` in five-second windows. It records sample count, median/p95/p99 frame intervals, derived median-rate estimate, draw calls, triangles, geometry/texture counts, canvas pixel dimensions, device pixel ratio, graphics mode and WebGL vendor/renderer strings where exposed. It does not report GPU utilization, JS heap usage, context-loss recovery, page load, or time-to-twin. Sampling forces continuous frames in a demand-rendered canvas, which perturbs idle behavior; the estimate is not a guaranteed application FPS.

## Foreground browser samples

Captured in the verified ChatGPT in-app browser on 2026-10-17 using WebGL 2. The WebGL renderer was **Intel UHD Graphics (0x468B), Direct3D11**; the laptop also has an NVIDIA GeForce RTX 4050, but the sampled context selected the integrated Intel GPU. CSS browser build/user-agent was not exposed. These samples were foreground only.

| Mode | Captured at | Samples / ~5 s | Frame interval median / p95 / p99 | Derived median rate | Draw calls | Triangles | Geometries / textures | Canvas px / DPR |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Standard | 09:12:26.814Z | 742 | 6.1 / 10.0 / 30.1 ms | 163.9/s | 72 | 90,018 | 44 / 3 | 861×581 / 1.25 |
| Low graphics | 09:12:52.167Z | 778 | 6.0 / 9.0 / 21.3 ms | 166.7/s | 56 | 55,344 | 44 / 3 | 689×465 / 1.25 |

The values come from a development browser session with the sampling probe's continuous-frame caveat above. They are not measured device FPS, load-test guarantees or operational-safety evidence. Standard versus low mode reduced measured draw calls by 16 and triangles by 34,674 in those individual snapshots. They are separate captures, not a controlled performance benchmark. A per-moving-vehicle sample and per-camera-motion sample were not recorded; performance under those operations remains unmeasured.

## Optimization and remaining measurements

The measured optimization is route-level lazy loading of Scenario Lab, Guided Demo, Model Lab, Judge Mode and Robustness Lab while preserving the Command Center and Digital Twin as the main path. No scene geometry/material/frame-loop rewrite was made without evidence. Low graphics continues to cap pixel ratio and disable shadows.

Remaining: browser build/version string; repeatable idle/flood/movement/camera samples at matched viewports; memory; WebGL loss/recovery; page load and time-to-visible-twin. No memory or context-recovery result is claimed.
