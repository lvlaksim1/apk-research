# Next Actions

1. Treat v0.31.0 at `5aab54adc807aff401b59d4c1018795246303b89` as the last verified product release; keep the two versioned installers, SHA-256 verification and isolated default/Google APIs AVD profiles.
2. If owner supplies the previously rejected XAPK, verify real installation and launch with the new ARM-compatible Android image. Real synthetic JNI execution is already proven, but does not guarantee universal compatibility.
3. Continue the older ACTIVE owner instruction: route HTTPS traffic from `com.evrasia` and similar applications that ignore Android system proxy through the application analyzer.
4. Re-examine owner archive `20261008T020126.928669Z-e336ad57.research.zip` if accessible; prior chat found 23 direct TCP/443 connections (21 to `evrasia.spb.ru`), but zero readable HTTP records. Verify before code-level diagnosis.
5. Preserve independent RAW PCAP, gRPC/MMAP, root, clean startup ordering, accurate HTTPS evidence provenance and explicit certificate/QUIC limitations.
6. Carry the HTTPS task through focused development, real app testing, mandatory main release gates and separate Setup/Update installers when verified.
7. Keep Android home-screen shortcut requirement cancelled; use neutral owner-visible HTTPS terminology.
