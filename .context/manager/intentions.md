# Manager intentions and commitments

## Completed — Continuous Screen stabilization and role selection
Status: completed.

## Completed — v0.24 Unified Session Evidence
Status: completed and released.

## Completed — v0.25 Transport and Protocol Analysis
Status: completed and released.

## Completed — v0.26 Investigator Workspace
Status: completed and released.

## Completed — v0.27 APK/XAPK Package Intake
Status: completed and released.

## Completed — v0.28 Direct GitHub Self-Update
Status: completed and released as v0.28.0.

Owner directive: add Settings controls to search for a new version and update directly from the latest GitHub release.

Delivered:
- explicit `Проверить обновления` action;
- hidden-until-needed `Обновить до <version>` control;
- latest stable GitHub Release discovery;
- exact installer/SHA256SUMS asset validation;
- direct download with local SHA-256 and size verification;
- detached wait → install-in-place → restart handoff on Windows;
- update blocking during research/managed operations;
- unit and GUI smoke coverage.

Completion evidence: PR #19 gates passed; main pipeline #138 passed on exact SHA `df2faf74a707cf99afa366433c34dc89cec37dcc`; GitHub Release v0.28.0 is published.

## Active — continuity and release integrity
Status: active.

Reconcile live product/release/CI before consequential changes and preserve all verified evidence/runtime boundaries.

No later product stage is active unless the owner defines it.
