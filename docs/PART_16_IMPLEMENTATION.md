# Part 16 implementation

Part 16 freezes the existing prototype and prepares an evidence-based handoff. It corrects Part 15 evaluation bucket boundaries, updates merged project status, adds a release approval matrix, central documentation index, Innotech kit, final rehearsal plan, candidate manifest process, release notes, and known-limitations register. Operational flood, ML, route, agent, approval, and mission logic is unchanged.

## Evaluation outcome categories

`backend/app/evaluation.py` uses `Decimal(str(value))` and a symmetric `0.01` tolerance. For optimized-minus-baseline objective delta:

- **Improved:** delta greater than `0.01`.
- **Tied:** delta between and including `-0.01` and `0.01`.
- **Lower:** delta less than `-0.01`.

The three categories are disjoint and exhaustive for finite values. Exact threshold values are tied. The report includes the category per scenario and in the CSV; its three summary counts must sum to the number of groups. Regression cases cover zero, both exact boundaries, values immediately outside both boundaries, and small positive/negative deltas.

## Release manifest

`scripts/write-release-manifest.ps1` generates a JSON manifest for the current checked-out commit and built frontend. It records the candidate label, Git SHA and branch, build timestamp, supported runtimes, dependency lock hashes, build asset hashes and sizes, model/calibration/support/dataset checksums, demo configuration, verification record references, browser status, and known limitations. Run it only after completing the local verification matrix:

```powershell
Push-Location frontend
npm ci
npm run build
Pop-Location
.\scripts\write-release-manifest.ps1
```

The default output is `artifacts/part16-release-manifest.json`, which `.gitignore` excludes. The script reads tracked source plus local model/build artifacts but does not copy databases, profiles, caches, or secrets into a package. It does not create a zip, tag a commit, create a GitHub Release, deploy, or submit to Innotech.

## Presentation handoff

`INNOTECH_SUBMISSION_KIT.md` gathers the verified project abstract, setup and demo instructions, evidence, pitches, and explicit fields the student team still needs to fill. No team-member names, institutional details, registration IDs, awards, contacts, or submission have been invented. The editable Markdown storyboard remains the source of slides; a binary PowerPoint was not produced.

## Scope boundary

The browser helper stopped because it could not verify the current Edge URL. Per the recovery instruction, no browser tool was retried or bypassed. Browser-based viewport, accessibility, reduced-motion, WebGL and visual stability checks are **BLOCKED by that tool safety restriction**, which is not evidence of an application defect. Existing Part 15 captures remain historical evidence only. No full responsive redesign or unverified operational feature was added.
