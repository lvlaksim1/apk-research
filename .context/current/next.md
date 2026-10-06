# Next Actions

1. Treat v0.23.0 / `cde0b56b5332f0b601221c9157efbd90da18fc33` as the current release baseline, but do not treat its experimental continuous-screen path as accepted.
2. On owner approval, make a focused corrective release before further Stage E feature work.
3. Preserve raw PCAP exactly; add explicit apk-research infrastructure classification for the exact sidecar control/media loopback ports and prevent those flows from normal app Timeline/Network/Packet correlations.
4. Remove the short steady-state read timeout from the media stream or otherwise separate handshake timeout from long-lived media reception. Add an idle-screen regression longer than 8 s.
5. Add a real-AVD assertion that sidecar-generated loopback flows cannot dominate or appear as ordinary app-correlated network evidence.
6. Consider disabling Continuous Screen in normal research sessions until the corrected implementation passes a new owner-side A/B archive.
7. Preserve canonical screenrecord, hidden Emulator → gRPC/MMAP → AndroidView and v0.10.5 startup/clean-launch sequencing.
8. Keep Audio Evidence and user-facing Virtual Display out of scope.
