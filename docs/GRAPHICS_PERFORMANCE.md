# Graphics performance record

## Build-size comparison

Production output from the Part 8 baseline and current visual implementation:

| Output chunk | Before | Part 9 | Change |
| --- | ---: | ---: | ---: |
| Main JS, minified | 707.92 kB | 708.16 kB | +0.24 kB |
| Main JS, gzip | 209.97 kB | 210.06 kB | +0.09 kB |
| Lazy CityScene, minified | 968.74 kB | 978.25 kB | +9.51 kB |
| Lazy CityScene, gzip | 258.73 kB | 261.82 kB | +3.09 kB |
| CSS | 59.72 kB | 61.45 kB | +1.73 kB |

The 3D viewport remains lazy-loaded. Total app JavaScript remains large, and Vite reports the scene chunk warning. A tested vendor split reduced the visible scene entry chunk but made the initial graph statically depend on 736.70 kB of Three.js core and 222.85 kB of React Three code; that experiment was reverted. The warning threshold was not changed.

## Scene geometry

For the baseline 72-building fixture (350 floors), 10 roads, 6 bridges and 32 trees, standard terrain increases from 825 vertices / 1,536 triangles to 3,185 vertices / 6,144 triangles. Low graphics retains the old terrain subdivision, removes streetlights and reduces window/tree instances. Repeating items share materials and instanced meshes.

## Measurements still pending

No authorized browser session was available for frame rate, draw calls, GPU memory, initial scene load, or viewport screenshots. Measure these on the actual presentation laptop using the checklist; record browser/GPU/viewport, seed, layer combination and whether low graphics is enabled. Do not substitute source object estimates for renderer statistics.
