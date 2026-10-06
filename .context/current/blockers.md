# Current Blockers and Unknowns

Last reconciled: 2026-10-07.

## Product blockers

No known release-blocking product defect is active. v0.23.1 is published and the Sidecar corrective behavior is owner-revalidated.

## Continuous Screen product role

There is no remaining stability/continuity blocker. Owner-side validation proves:
- 59.005 s idle/no-frame survival and resume;
- successful >170 s operation;
- uninterrupted evidence through canonical screenrecord chunk rotation;
- clean decode/shutdown;
- Sidecar infrastructure isolation from ordinary derived network evidence.

The remaining issue is evidence quality/role, not reliability. Current Continuous Screen capture is 540×960 / 2 Mbit/s; canonical screenrecord is 1080×1920. Replacing canonical screenrecord outright at the current profile would reduce spatial evidence detail by 4× in pixel count.

An explicit owner decision is required:
- retain screenrecord as canonical high-resolution evidence and promote Continuous Screen as a stable continuous/timeline source; or
- raise/revalidate Continuous Screen quality before considering sole canonical replacement.

## WHPX

WHPX is advisory/non-publication-gating.
