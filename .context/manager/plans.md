# Manager plans

## Default plan for product changes

1. Reinstate from `context` and reconcile live `main`, latest release and relevant CI.
2. Preserve the current product baseline; use a dedicated feature/fix branch for substantive work.
3. Make the minimum coherent change and keep runtime/capture/evidence boundaries explicit.
4. Run compile/tests and the relevant specialized regression tests before promotion.
5. For release-bound changes, rely on the existing main pipeline: CI → real AVD acceptance → Windows standalone/GUI/installer smoke → clean-Windows provisioning → Publish Release.
6. For evidence/network changes, verify with a real Research ZIP when owner evidence is available.
7. After verified durable findings, persist semantic changes to the authoritative `context` branch and reseal manager state.

## Context maintenance plan

- Keep `main` discovery-only for Context Capsule bootstrap.
- Persist manager identity, BDI state, memory and current working views only on `context`.
- Never let a temporary feature branch become manager-state authority.
- Keep secrets, transient runtime state and hidden reasoning out of the capsule.
