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
Status: completed and released.

## Completed — v0.29.1 reliable updater handoff
Status: completed and released.

Owner-reported defect: update download and verification completed, restart was announced, GUI closed, but installation/restart did not occur.

Delivered:
- removed hidden PowerShell relay from the updater;
- directly launches the verified Inno Setup process before GUI exit;
- lets Inno Setup own the post-update relaunch;
- persists handoff and installer logs;
- adds real Windows parent-exit upgrade acceptance from public v0.29.0 to the candidate release;
- preserves same-AppId in-place update semantics and SHA-256 verification.

Completion evidence: PR #21 gates passed; main pipeline #140 passed on exact SHA `ae4450ba662299c30199742ba4b1d2bbcdb27601`; GitHub Release v0.29.1 is published.

## Active — continuity and release integrity
Status: active.

Reconcile live product/release/CI before consequential changes and preserve all verified evidence/runtime boundaries.

No later product stage is active unless the owner defines it.
