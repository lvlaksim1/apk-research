# Manager intentions and commitments

## Completed — v0.24 Unified Session Evidence
Status: completed and released.

## Completed — v0.25 Transport and Protocol Analysis
Status: completed and released.

## Completed — v0.26 Investigator Workspace
Status: completed and released.

## Completed — v0.27 APK/XAPK Package Intake
Status: completed and released.

## Completed — v0.28 Direct GitHub Self-Update
Status: completed and released.

## Completed — v0.29 corrective usability/runtime release
Status: completed and released as v0.29.0.

Owner directives covered by v0.29:
- replace the technical placeholder icon with a proper application icon;
- fix XAPK installation failures caused by ABI mismatch/selection;
- expose an obvious way to install and run apps in the emulator and open Android home;
- ensure the installer updates the existing installation rather than uninstalling/reinstalling it.

Delivered and verified:
- project-owned Windows icon;
- ABI-aware XAPK split filtering and clear mismatch diagnostics;
- explicit install/launch/home controls;
- explicit in-place installer update contract;
- full CI, real AVD, Windows desktop/installer, clean-Windows provisioning and release publication.

Completion evidence: PR #20 gates passed; main pipeline #139 passed on exact SHA `81a565dbc3b4c41712b8a6e3c3ba8020060ff5a2`; GitHub Release v0.29.0 is published.

## Active — continuity and release integrity
Status: active.

Reconcile live product/release/CI before consequential changes and preserve all verified evidence/runtime boundaries.

No later product stage is active unless the owner defines it.
