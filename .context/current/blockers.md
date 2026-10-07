# Current Blockers and Unknowns

Last reconciled: 2026-10-07.

## Product blockers

No known release-blocking product defect is active. v0.29.1 is published and all mandatory release gates passed on exact SHA `ae4450ba662299c30199742ba4b1d2bbcdb27601`.

## Update bootstrap boundary

The broken relay exists in already-installed v0.28.0/v0.29.0 binaries. Those binaries cannot be repaired retroactively by a release they fail to launch. A user affected by that defect must manually install v0.29.1 once. From v0.29.1 onward the corrected direct-installer handoff is present.

## Continuous Screen

One release-pipeline attempt reported `failed-experimental` while the session/ZIP and other acceptance layers passed. An exact rerun passed. No reproducible screen-collector regression is currently established.

## WHPX

WHPX remains advisory/non-publication-gating.
