# DEC-20261006 — v0.22 verified release baseline

Status: accepted.

## Decision

Adopt apk-research v0.22.0 at `d58265584223246974fb641f02e0dd3fb8d3f4f1` as the current verified product baseline.

v0.22 completes the first Stage E increment by adding packet-to-action temporal evidence and direct Packet → Timeline navigation while preserving the archived Timeline as the action-window source and raw PCAP as the network source of truth.

## Verification

Main pipeline #125 (`37406246024`) completed SUCCESS including exact-SHA CI, real AVD Research ZIP acceptance, Windows standalone/installer smoke, clean-Windows provisioning and GitHub Release publication.

Installer SHA-256: `d6f7ae647d755455a374189a3731e15057fc74ec88c4b9a846143145ebb0ae8a`.

## Evidence boundary

Packet/action relations require both the selected flow reference and membership in the existing archived target-time window. They remain `temporal-only` and `causal_claim=false`.

## Authority

Verified repository + verified CI/release evidence, reconciled 2026-10-06.
