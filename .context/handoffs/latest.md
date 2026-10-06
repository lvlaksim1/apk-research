# Latest Handoff

Generation: 8
Date: 2026-10-06

Persistent manager: `apk-research-project-manager`.

Authority:
- manager state: `context`;
- product: `main`.

Release baseline remains **apk-research v0.23.0** at `cde0b56b5332f0b601221c9157efbd90da18fc33`.

The owner supplied real archive `20261006T105244.785342Z-3076e6ba.research.zip`. Canonical research evidence is healthy: all checksums verify, session complete/degraded=false, COLD launch, canonical screenrecord complete, tcpdump 0 kernel drops, socket attribution works, and no com.evrasia crash/ANR is present.

However two real defects are now proven in the experimental continuous-screen path:

1. Sidecar adb-reverse control/media traffic appears as ordinary loopback flows. Those two flows account for 11,993/12,419 TCP/UDP flow packets and 7,208,463/7,396,346 flow bytes; the media flow is correlated with 15/16 user actions.

2. Continuous screen records only about 10.04 s and ends `failed-experimental`. The sidecar C2 encoder reports repeat-previous-frame unsupported, while the host media socket has an 8 s timeout. The archive contains an 8.624 s target-time idle gap between the last media PTS and the next user action, explaining the host read timeout.

Canonical screenrecord remains authoritative and healthy. Continuous-screen promotion is blocked. Preferred next work is a focused corrective release before further feature development.
