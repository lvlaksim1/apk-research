# Current Blockers and Unknowns

Last reconciled: 2026-10-06.

## Verified owner-side defects

### Experimental continuous screen

A real v0.23 owner archive shows `failed-experimental`. It captured only about 10.04 s of media PTS while canonical screenrecord captured about 66.10 s. The host reports `Unable to read Android sidecar media stream`, stop statistics are absent and sidecar cleanup is incomplete.

Code/evidence correlation identifies the immediate failure mechanism: the binary media socket retains the generic 8 s timeout, while the Android C2 encoder explicitly reports that `repeat-previous-frame-after` is unsupported. A static display can therefore legitimately produce no packets for more than 8 s, causing the host receiver to time out.

### Sidecar network self-contamination

The same archive proves that adb-reverse sidecar traffic is included as ordinary 127.0.0.1 TCP flows in `network-flows.json` and Timeline. Sidecar control+media account for 96.57% of TCP/UDP flow packets and 97.46% of TCP/UDP captured bytes, and the media flow is correlated with 15/16 user actions.

Raw PCAP remains correct. The defect is in infrastructure-flow classification/presentation/correlation.

## Canonical evidence health

The required collectors are healthy: session complete, degraded=false, checksums valid, COLD launch, canonical screenrecord complete, tcpdump 0 kernel drops, socket attribution functioning, and no target-app crash/ANR found.

## Continuous screen promotion

Promotion is blocked. The collector must remain experimental/non-canonical until owner-side A/B evidence passes after correction.

## WHPX

WHPX is advisory/non-publication-gating.
