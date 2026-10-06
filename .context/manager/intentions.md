# Manager intentions and commitments

## Completed — v0.23 owner-archive defect correction

Status: completed in v0.23.1.

The two owner-proven v0.23.0 Sidecar defects were corrected without changing RAW authority or the proven Android runtime:
- Sidecar loopback traffic remains in raw PCAP but is excluded from ordinary app derived evidence using exact archived dynamic ports;
- long-lived media reception no longer inherits the short handshake timeout.

PR #14 and main pipeline #127 both passed real-AVD idle/infrastructure regressions.

## Proposed — owner-side v0.23.1 revalidation

Status: proposed, non-blocking.

When the owner supplies a new v0.23.1 Research ZIP, verify that:
- Continuous Screen survives idle periods and completes cleanly;
- Sidecar control/media packets are counted as infrastructure but absent from ordinary app flows and action correlations;
- canonical screenrecord remains complete.

## Active — evidence-preserving Stage E continuation

Status: active after owner-side revalidation or in parallel for low-risk presentation work.

Continue deeper evidence intelligence from the verified v0.23.1 baseline, preserving RAW-first provenance, capture-bounded semantics and explicit confidence boundaries.

## Active — continuity and release integrity

Status: active.

Reconcile live `main`, releases and CI before consequential changes; preserve v0.10.5 startup sequencing, gRPC/MMAP display/input and commit-triggered release gates.
