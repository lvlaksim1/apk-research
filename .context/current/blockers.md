# Current Blockers and Unknowns

Last reconciled: 2026-10-07.

## Product blockers

No known release-blocking product defect is active. v0.23.1 is published, all publication gates passed, and the two owner-proven v0.23.0 Sidecar defects are owner-revalidated as corrected.

## Continuous Screen promotion

Continuous Screen remains experimental/non-canonical for one narrow reason: the supplied owner-side v0.23.1 session lasted about 138 s and did not cross the canonical `screenrecord` 170 s chunk boundary.

The real archive already proves:
- survival and resume after a 59.005 s no-frame interval;
- no Sidecar leakage into ordinary app flow/action evidence;
- clean completion;
- close visual/timing equivalence with canonical screenrecord during the tested interval.

The remaining promotion gate is long-session continuity across at least one canonical chunk rollover, followed by an explicit owner promotion decision.

## WHPX

WHPX is advisory/non-publication-gating.
