# Manager intentions and commitments

## Active — v0.23 real-archive defect correction

Status: active pending owner execution directive.

The owner-side v0.23 archive proves that the experimental continuous-screen path is not ready for canonical use and currently contaminates normalized network analysis with apk-research sidecar traffic. The next corrective release should preserve the healthy canonical research chain while removing these effects.

Preferred minimal correction:
- keep raw PCAP untouched;
- classify exact dynamically allocated sidecar control/media loopback flows as apk-research infrastructure and exclude them from normal app Timeline/Network/Packet correlations by default;
- prevent legitimate idle periods from killing continuous media reception (the steady-state media socket must not inherit the short handshake timeout);
- strengthen real-AVD tests with an idle interval longer than the media timeout and assertions that sidecar infrastructure flows do not enter ordinary app correlation.

If strict forensic isolation is preferred, temporarily disabling the experimental continuous-screen collector in normal research sessions is lower risk than leaving the current behavior active.

## Active — evidence-preserving Stage E continuation

Status: active after correction.

Continue deeper evidence intelligence from the verified v0.23.0 baseline only after the owner-side defects are corrected, preserving RAW-first provenance, capture-bounded semantics and explicit confidence boundaries.

## Active — continuity and release integrity

Status: active.

Reconcile live `main`, releases and CI before consequential changes; preserve v0.10.5 startup sequencing, gRPC/MMAP display/input and commit-triggered release gates.
