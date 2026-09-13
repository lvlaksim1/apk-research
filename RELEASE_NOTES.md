# Mobile Research v0.1.0

First stable **Research Session Core** release.

## What this release proves

Mobile Research can execute the complete evidence pipeline against a real rooted Android Emulator:

```text
target/package preflight
→ metadata
→ logcat + screen + raw PCAP
→ package launch
→ health checks
→ STOP
→ complete/partial state resolution
→ SHA-256 Research ZIP
→ semantic timeline/evidence audit
```

## Main capabilities

- ADB target discovery and metadata.
- Atomic research-session state machine.
- Full raw device/package metadata.
- Continuous logcat capture.
- Chunked Android screenrecord capture with Winscope-v2 absolute frame timing.
- Raw tcpdump PCAP independent of MITM.
- Preservation of partial evidence on collector failures.
- Verified Research ZIP with full checksum coverage.
- Semantic audit of collector state, lifecycle sequence, host/target clock skew, PCAP/logcat coverage and screen timing.

## Real acceptance evidence

Before release freeze, two consecutive real AVD-RESEARCH runs completed successfully. The stricter second acceptance reported:

- session status: `complete`
- validation issues: `0`
- PCAP packets: `12`
- logcat entries: `914`
- screen frames: `139`
- last screen frame → STOP gap: `0.536 s`
- max host/target clock skew: `0.942 s`

The release workflow also requires fresh Windows CI and real AVD acceptance success for the exact release commit before it creates the tag/release.

## Distribution

Release assets:

- Python wheel
- source distribution (sdist)
- `SHA256SUMS.txt`

Python requirement: **3.11+**. ADB is an external runtime dependency.

## Scope boundaries

v0.1.0 intentionally does not include GUI, MITM/TLS decryption, AVD-PLAY acceptance, Physical Device acceptance, static APK analysis, Android Research Agent, runtime instrumentation or automatic protocol interpretation.
