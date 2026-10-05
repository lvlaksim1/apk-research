# Manager beliefs

## Product baseline and latest release

The product authority is `main`. The current verified product baseline and latest published release are `apk-research v0.18.0` at commit `4d9f3097406502ec397416ea3e7ce07264e74814`. Release asset `apk-research-setup_v0.18.0.exe` has SHA-256 `dcae7555a407ba840577e22e4447d20e4afc44804582e8ab8954d40406d9f2a9`.

Main pipeline #120 (`37390818056`) completed successfully for the exact release SHA. It passed CI, real AVD research acceptance, generated Research ZIP verification, Windows standalone/self-test/GUI smoke, installer build/install/smoke, clean-Windows managed Android provisioning and release publication.

- source: GitHub repository main, main pipeline #120 and GitHub Release v0.18.0, reconciled 2026-10-06
- authority: verified-repository + verified-ci

## v0.18.0 Raw / Packet Inspector evidence boundary

v0.18.0 closes the in-app raw-network inspection gap without changing capture. A selected normalized TCP/UDP flow is resolved against the original `01_raw/network/traffic.pcap` using the same direction-independent canonical flow identity as the normalized inventory. Packet presentation retains the original PCAP packet index, record/frame byte offsets, target timestamp, endpoints and lengths; raw hex preview is bounded and encrypted payload is not represented as plaintext.

The release real-AVD gate additionally validated Packet Inspector against a genuinely generated Research ZIP: the selected packet count had to equal the normalized flow packet count and raw PCAP offsets had to be valid.

- source: release commit `4d9f3097406502ec397416ea3e7ce07264e74814` and pipeline #120
- authority: verified-repository + verified-ci

## v0.16.1 real-world acceptance

The QUIC false-positive defect from v0.16.0 was corrected in v0.16.1. A user-provided real Research ZIP verified that DNS traffic was no longer misclassified as QUIC, packet accounting remained exact, and the user accepted v0.16.1 as stable.

- source: owner-provided Research ZIP and verified archive analysis from the apk-research development session
- authority: owner-evidence

## Proven Android runtime baseline

The validated runtime path is hidden Android Emulator (`-qt-hide-window`) → Emulator gRPC → MMAP framebuffer → AndroidView, with input through persistent gRPC pointer events. v0.10.5 restored and defines the proven clean-launch sequencing baseline; it must not be changed casually.

- source: repository README.md / CHANGELOG.md and accepted release history
- authority: verified-repository

## Evidence semantics

Raw PCAP remains the primary network source of truth. Package ownership attribution, normalized flows, Timeline correlation, QUIC/HTTP3 metadata, Unified Evidence Explorer and Packet Inspector are derived/presentation evidence. Action ↔ Flow correlation is temporal-only and must not be promoted into a causal claim.

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

## WHPX acceptance status

Separate WHPX acceptance remains advisory/non-publication-gating. A cancelled or delayed WHPX run is not evidence of product failure unless a specific WHPX claim is being evaluated.

- source: repository release workflow and prior reconciled WHPX behavior
- authority: verified-repository + verified-ci

## scrcpy-derived scope decision

The owner accepted the useful scrcpy-derived directions except Audio Evidence and Virtual Display. Those two areas are explicitly out of the current apk-research roadmap. Retained directions are: a bounded Android-side app_process sidecar, continuous device-PTS screen evidence, richer multi-touch/control, geometry-generation protection for input, and later opt-in keyboard/clipboard improvements. The proven gRPC/MMAP live display/input path remains authoritative and is not to be replaced by scrcpy-style encoded mirroring.

- source: explicit owner directive in project dialogue on 2026-10-06 following scrcpy v5.0 review
- authority: owner-directive
