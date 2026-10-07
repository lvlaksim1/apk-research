# Manager beliefs

## Product baseline and latest release

The product authority is `main`. The current verified product baseline and latest published release are **apk-research v0.28.0** at `df2faf74a707cf99afa366433c34dc89cec37dcc`.

Release asset `apk-research-setup_v0.28.0.exe` has SHA-256 `9c5444503b6306497ebe5acac87040830d0eefa2fbdb16c06cd521b50f8bd61e` and size 36,436,053 bytes. GitHub Release v0.28.0 was published on 2026-10-07 for the exact release SHA after main pipeline #138 passed CI, real AVD Research ZIP acceptance, real XAPK install acceptance, Windows standalone/self-test/GUI/installer checks, clean-Windows managed Android provisioning, checksum verification and release publication.

The public `releases/latest` endpoint returns v0.28.0 with the exact versioned installer and `SHA256SUMS.txt`, matching the runtime update-discovery contract.

- source: GitHub main, PR #19, main pipeline #138 and GitHub Release v0.28.0, reconciled 2026-10-07
- authority: owner-directive + verified-repository + verified-ci

## Completed roadmap through v0.28

- v0.18.0: Raw / Packet Inspector.
- v0.19.0: Android sidecar foundation.
- v0.20.0: Continuous Screen foundation.
- v0.21.0: interaction completeness.
- v0.22.0: Packet ↔ Action temporal evidence.
- v0.23.0: Transport Session Evidence.
- v0.23.1: Sidecar isolation + idle stability.
- v0.24.0: Unified Session Evidence.
- v0.25.0: Transport and Protocol Analysis.
- v0.26.0: Investigator Workspace.
- v0.27.0: first-class APK/XAPK package intake.
- v0.28.0: verified direct GitHub self-update.

## v0.28 update behavior

Update discovery is explicit/user-triggered, not background polling. A newer stable release is offered only when GitHub provides a strict semantic version, the exact `apk-research-setup_v<version>.exe`, and `SHA256SUMS.txt`.

The downloaded installer is size-checked and SHA-256 checked locally. A detached Windows handoff waits for the running process to exit, installs into the same directory and restarts the executable. Research/managed-operation activity blocks update installation.

## Protected semantics/runtime

All v0.24-v0.27 evidence and package-intake semantics remain unchanged. Raw PCAP remains authoritative; action/network links remain temporal-only/non-causal; protocol analysis remains captured-packets-only; analyst workspace metadata is not evidence. Hidden Emulator → gRPC/MMAP → AndroidView, v0.10.5 startup sequencing and the accepted dual-source screen model remain protected. Audio Evidence and user-facing Virtual Display remain out of scope. WHPX remains advisory/non-publication-gating.
