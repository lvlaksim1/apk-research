# DEC-20261006 — v0.18.0 verified release baseline

Status: accepted.

## Decision

Treat apk-research v0.18.0 at `4d9f3097406502ec397416ea3e7ce07264e74814` as the current verified product baseline and mark roadmap Stage A (Raw / Packet Inspector) complete.

Advance the active roadmap to Stage B: Android sidecar foundation.

## Evidence

Main pipeline #120 (`37390818056`) completed successfully for the exact release SHA, including CI, real AVD Research ZIP acceptance with Packet Inspector count/offset validation, Windows standalone/GUI/install smoke, clean-Windows managed Android provisioning, checksum verification and release publication.

GitHub Release v0.18.0 published installer `apk-research-setup_v0.18.0.exe` with SHA-256 `dcae7555a407ba840577e22e4447d20e4afc44804582e8ab8954d40406d9f2a9`.

## Boundary

This release changes post-capture presentation/inspection only. Existing runtime, collectors, Research ZIP schemas, raw PCAP authority, Action ↔ Flow temporal-only semantics and v0.10.5 startup/clean-launch sequencing remain unchanged.
