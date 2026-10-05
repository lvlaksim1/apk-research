# Project Constraints

## Required invariants

- Do not require Python or command-line operation for normal end-user use.
- Keep the Android Emulator managed/embedded by apk-research.
- Preserve the proven hidden Emulator → gRPC/MMAP → AndroidView runtime unless verified evidence requires architectural change.
- Preserve v0.10.5 startup/collector/clean-launch sequencing unless a real defect demonstrates that it must change.
- Do not reintroduce obsolete DWM/native/ADB display/input fallback chains as normal recovery paths.
- Raw PCAP remains primary evidence; derived views must retain provenance and must not rewrite the source of truth.
- Action ↔ Flow correlation is temporal-only and must never be presented as proven causality.
- QUIC/HTTP3 labels require protocol evidence; port number alone is insufficient.
- Stable release installers include the version in the filename.
- Stable release publication is commit-triggered through repository workflows; do not substitute ad-hoc manual release publication.
- Keep temporary verification workflows/artifacts out of the final product tree.
- Product authority is `main`; persistent manager state is `context`; feature branches do not inherit either authority.
- Do not persist credentials, tokens, cookies, private keys, hidden reasoning or unnecessary sensitive data in repository context.

## Working preferences derived from owner directives

- Prefer systematic root-cause fixes over layered fallback workarounds.
- When the owner says to continue/execute and the task is well-defined, proceed autonomously rather than repeatedly asking for confirmation.
- For regressions discovered by real Research ZIP evidence, turn the observed pattern into a regression test when practical.
