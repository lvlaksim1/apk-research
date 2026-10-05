# DEC-20261005 — Persistent Project Manager bootstrap

Status: accepted.

## Decision

Install the canonical pinned Project Manager into `lvlaksim1/apk-research` using a permanent authority split:
- manager-state authority: `context`;
- product authority/discovery branch: `main`.

Pin components to the verified `repo-factory/components.lock.json` coordinates:
- Context Capsule Core v1.3.1: `2ef41a5ed57ae514cc5980065560d7e55d5e4b9a`;
- Project Manager v2.0.0-dev: `9d6a2f69d38d880c44ea59c9b3d31b406cc5bcf1`.

Use stable manager ID `apk-research-project-manager`.

## Rationale

apk-research is developed through many temporary feature/fix branches, so a permanent manager-state branch prevents transient work branches from becoming durable-context authority and lets `main` remain product authority.

## Authority

Explicit owner directive on 2026-10-05.
