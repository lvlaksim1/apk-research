# Manager beliefs

## Product baseline and latest release

The product authority is `main`. At manager bootstrap, the product code baseline and latest published release are `apk-research v0.17.0` at commit `202d42fcfcccf03e0a9189a1a97f6e57be3578b8`. Release asset `apk-research-setup_v0.17.0.exe` has SHA-256 `cdf5b5697f2c5af4d64d6d47f5c81326115b898929c4708e55082d68dce65b67`.

- source: GitHub repository main and GitHub Release v0.17.0, reconciled 2026-10-05
- authority: verified-repository

## v0.16.1 real-world acceptance

The QUIC false-positive defect from v0.16.0 was corrected in v0.16.1. A user-provided real Research ZIP verified that DNS traffic was no longer misclassified as QUIC, packet accounting remained exact, and the user accepted v0.16.1 as stable.

- source: owner-provided Research ZIP and verified archive analysis from the apk-research development session
- authority: owner-evidence

## Proven Android runtime baseline

The validated runtime path is hidden Android Emulator (`-qt-hide-window`) → Emulator gRPC → MMAP framebuffer → AndroidView, with input through persistent gRPC pointer events. v0.10.5 restored and defines the proven clean-launch sequencing baseline; it must not be changed casually.

- source: repository README.md / CHANGELOG.md and accepted release history
- authority: verified-repository

## Evidence semantics

Raw PCAP remains the primary network source of truth. Package ownership attribution, normalized flows, Timeline correlation, QUIC/HTTP3 metadata and the Unified Evidence Explorer are derived evidence. Action ↔ Flow correlation is temporal-only and must not be promoted into a causal claim.

- source: repository README.md, RELEASE_NOTES.md and normalized-evidence implementation
- authority: verified-repository

## Product UX contract

apk-research is a standalone Windows GUI application. Normal use must not require the user to install Python or operate a CLI; the Android Emulator is managed by the application. Installer filenames include the product version.

- source: explicit owner directives during apk-research development
- authority: owner-directive

## Repository release contract

Stable releases are produced by the commit-triggered main pipeline, not by ad-hoc/manual release publication. Temporary verification workflows and build artifacts must not remain in the final product tree.

- source: explicit owner directives plus current repository workflows
- authority: owner-directive

## Manager and product authority split

The durable Project Manager state authority is branch `context`; product baseline authority remains `main`. Feature/runtime branches are neither authority merely because work occurs there.

- source: owner authorization on 2026-10-05 and canonical Context Capsule permanent-authority protocol
- authority: owner-directive

## WHPX acceptance status for v0.17.0

The separate WHPX acceptance run #112 (`35174782512`) finished `cancelled` after having been non-gating for release publication. This is not evidence of a v0.17.0 product failure. Re-run WHPX only if a future claim specifically requires that environment.

- source: GitHub Actions run 35174782512 reconciled 2026-10-05
- authority: verified-ci

## scrcpy-derived scope decision

The owner accepted the useful scrcpy-derived directions except Audio Evidence and Virtual Display. Those two areas are explicitly out of the current apk-research roadmap. Retained candidates are: a bounded Android-side app_process sidecar, continuous device-PTS screen evidence, richer multi-touch/control, geometry-generation protection for input, and later opt-in keyboard/clipboard improvements. The proven gRPC/MMAP live display/input path remains authoritative and is not to be replaced by scrcpy-style encoded mirroring.

- source: explicit owner directive in project dialogue on 2026-10-06 following scrcpy v5.0 review
- authority: owner-directive
