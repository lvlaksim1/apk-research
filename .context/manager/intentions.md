# Manager intentions and commitments

## Completed — v0.23 owner-archive defect correction

Status: completed in v0.23.1 and owner-revalidated.

The two owner-proven v0.23.0 Sidecar defects were corrected without changing RAW authority or the proven Android runtime:
- Sidecar loopback traffic remains in raw PCAP but is excluded from ordinary app derived evidence using exact archived dynamic ports;
- long-lived media reception no longer inherits the short handshake timeout.

PR #14 and main pipeline #127 both passed real-AVD idle/infrastructure regressions.

## Completed — owner-side v0.23.1 defect revalidation

Status: completed.

Archive `20261006T230500.602195Z-1206ec46.research.zip` proves that Continuous Screen survives and resumes after a 59.005 s no-frame interval, Sidecar traffic remains preserved only as RAW/infrastructure evidence, canonical screenrecord remains complete, and post-idle interaction is captured normally.

## Active — Continuous Screen promotion gate

Status: active.

Before recommending promotion from experimental/non-canonical status, obtain one owner-side session that crosses at least one canonical `screenrecord` 170 s chunk boundary. Compare coverage around rollover, Sidecar continuity, frame/timestamp consistency and clean completion. Promotion then requires an explicit owner decision.

## Active — evidence-preserving Stage E continuation

Status: active after owner-side revalidation or in parallel for low-risk presentation work.

Continue deeper evidence intelligence from the verified v0.23.1 baseline, preserving RAW-first provenance, capture-bounded semantics and explicit confidence boundaries.

## Active — continuity and release integrity

Status: active.

Reconcile live `main`, releases and CI before consequential changes; preserve v0.10.5 startup sequencing, gRPC/MMAP display/input and commit-triggered release gates.
