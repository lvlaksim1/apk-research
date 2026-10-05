# Project Rules

- Canonical product name is `apk-research`.
- Normal user workflow is GUI-first and standalone; no external Python installation is required.
- Android Emulator/runtime is managed by the application.
- v0.10.5 clean-launch/startup ordering is the proven baseline.
- Avoid fallback chains that mask a broken primary runtime path; repair the primary path systematically.
- Raw PCAP is source of truth for network evidence.
- Package/socket attribution strength and temporal action correlation must remain explicitly separated.
- Action ↔ Flow correlation is `temporal-only`; no causal claim without stronger evidence.
- QUIC/HTTP3 classification must be evidence-driven and regression-protected.
- Final installer filenames contain the version.
- Stable releases are commit-triggered; do not manually bypass release gates.
- Remove temporary verification workflows/artifacts from final product state.
- Prefer public repositories where practical and keep repository state free of unnecessary artifacts.
- Use real Research ZIP evidence to validate user-visible forensic behavior when available.
- Manager state is authoritative only on `context`; `main` is product authority plus discovery bootstrap.
- Never persist credentials, tokens, cookies, private keys or hidden reasoning in Context Capsule.
