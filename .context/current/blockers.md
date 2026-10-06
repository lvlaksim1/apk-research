# Current Blockers and Unknowns

Last reconciled: 2026-10-06.

## Product blockers

No known release-blocking product defect is active. v0.23.1 is published and all publication gates passed.

## Owner-side revalidation

A new owner-provided v0.23.1 Research ZIP has not yet been inspected. CI/real-AVD proves the exact regression cases, but a real owner session is still valuable to confirm the previous 66-second pattern no longer reproduces and that Sidecar infrastructure is absent from ordinary app correlations.

## Continuous screen promotion

Continuous Screen remains experimental/non-canonical. v0.23.1 fixes the observed idle timeout and evidence contamination, but promotion to canonical still requires separate owner-side A/B evidence and an explicit decision.

## WHPX

WHPX is advisory/non-publication-gating.
