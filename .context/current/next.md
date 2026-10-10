# Next Actions

1. Continue PR #32 (branch feature/v0.34-emulator-controls-network-evidence), exact latest SHA 8c1dbcc81fa3620ed96b30300211c90fb7872ec3, with published baseline v0.33.0 main 3f3f1144e0ea8944a065e7d5950fd07fd1e17abf.
2. Check full CI, Android AVD with required expanded ZIP files, and Windows UI/installer/update at the latest SHA. Deal with real failures, distinguish transient Android Settings ADB 255 from source errors; do not bypass release gates.
3. Once all pass, mark PR #32 ready, squash merge to main, let main pipeline run, verify GitHub Release v0.34.0 exact commit and SHA256SUMS for separate Setup and Update installers; provide direct update installer link.
4. Advance context capsule from development to published after release.
5. Preserve only two main tabs Research/HTTPS Online, independent RAW PCAP, full response bodies, gRPC/MMAP, ARM64, user data, and no owner-cancelled Android launcher shortcut.
6. User-facing language: neutral Russian terms only. Optional DNS/TLS data may be absent due encryption, QUIC or fragmentation; action links are temporal candidates. Full screen-video remains a standard Research ZIP collector.
