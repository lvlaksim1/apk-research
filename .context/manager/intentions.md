# Manager intentions and commitments

## Completed — v0.23 owner-archive defect correction

Status: completed in v0.23.1 and owner-revalidated.

The two owner-proven v0.23.0 Sidecar defects were corrected without changing RAW authority or the proven Android runtime:
- Sidecar loopback traffic remains in raw PCAP but is excluded from ordinary app derived evidence using exact archived dynamic ports;
- long-lived media reception no longer inherits the short handshake timeout.

PR #14, main pipeline #127 and two real owner-side v0.23.1 archives validate the correction.

## Completed — Continuous Screen technical validation

Status: completed.

Owner archives prove:
- resume after a 59.005 s no-frame static interval;
- one uninterrupted Sidecar stream through a canonical 170 s screenrecord rollover;
- 66 continuous frames inside the 1.965848 s canonical rollover frame gap;
- capture of an owner action during that canonical gap;
- clean H.264 decode/collector shutdown;
- Sidecar infrastructure isolation from ordinary derived app network evidence.

## Completed — Continuous Screen product-role decision

Status: completed by explicit owner decision.

Accepted dual-source role:
- Continuous Screen is the stable continuous/timeline screen-evidence source;
- canonical Android screenrecord remains the high-resolution source;
- sole-source replacement is deferred until Continuous Screen quality is raised and revalidated.

## Active — evidence-preserving Stage E continuation

Status: active.

Continue deeper evidence intelligence from the verified v0.23.1 baseline, preserving RAW-first provenance, capture-bounded semantics and explicit confidence boundaries.

## Active — continuity and release integrity

Status: active.

Reconcile live `main`, releases and CI before consequential changes; preserve v0.10.5 startup sequencing, gRPC/MMAP display/input and commit-triggered release gates.
