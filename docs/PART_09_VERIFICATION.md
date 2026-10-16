# Part 9 verification

## Foundation and branch

- Base: `main` at the Part 8 merge commit `40b5295beb1bf89bdf5415000d6aaed71ad1b5d4` (verified as ancestor of the fetched `origin/main` before the Part 9 branch was created).
- Working branch: `feature/part-09-digital-twin-realism`.
- Baseline before visual edits: backend 64 tests passed; frontend 23 tests passed; ESLint, TypeScript and production build passed.
- Baseline scene chunk: `CityScene` 968.74 kB minified / 258.73 kB gzip; main JS chunk 707.92 kB / 209.97 kB gzip.
- The baseline camera was orthographic at `[520, 500, 570]`, zoom `0.9`, looking at the origin. The standard renderer used a 20 m terrain grid, shadow maps and DPR `[1, 1.5]`.

## Automated evidence

The visual-data tests cover flood-depth band/color/opacity mapping, hospital/shelter/home appearance profiles, and interpolation between authoritative terrain samples. Existing mission-route tests cover a right-angle corner, bridge elevation, heading and endpoint sampling. The frontend suite also verifies the user-facing names of layer controls.

Local final validation: backend Pytest **64 passed**; frontend Vitest **26 passed across 10 files**; ESLint **passed**; TypeScript **passed**; API contract generation **passed**; production build **passed**. Pytest needed a backend-local isolated temporary directory because the shared Windows pytest temp root returned an access-denied error; all 64 tests passed with that isolated runner directory. Hosted checks should be reported separately after GitHub Actions completes.

## Browser review

Status: pending. The computer-use helper could not establish the active browser URL and stopped its browser workflow. No screenshots, visual FPS, draw-call, GPU, or page-load measurements are claimed. Use [VISUAL_DEMO_CHECKLIST.md](VISUAL_DEMO_CHECKLIST.md) for a reproducible manual review.

## Bundle measurement

Baseline and Part 9 builds use the same Vite/Rolldown production build. The Part 9 visual additions increased the lazy `CityScene` chunk by about 9.5 kB minified and 3.1 kB gzip in the measured final build. A manual Three.js vendor split experiment was reverted because it moved Three/Fiber dependencies into the initial dependency chain (736.70 kB `three-core` and 222.85 kB `react-three` chunks). The existing lazy scene boundary keeps 3D code deferred until its view is used; no warning threshold was raised.
