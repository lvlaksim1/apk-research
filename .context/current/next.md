# Next Actions

1. Branch v0.22 work from current `main` v0.21.0 baseline.
2. Extend Packet Inspector to load action correlation windows from `02_normalized/research-timeline.json`.
3. For packets belonging to the selected flow, attach only those actions whose existing temporal window contains the packet timestamp and whose existing network correlation references that flow.
4. Preserve explicit `temporal-only` and `causal_claim=false`; do not manufacture causality or rewrite Timeline evidence.
5. Add packet-table Action column, searchable action IDs/labels, detailed window provenance and Packet → Timeline navigation.
6. Add unit regression tests for boundaries, multiple actions and no-match behavior.
7. Strengthen real-AVD acceptance so any matched packet/action relation is validated against the archived Timeline window and flow IDs.
8. Run CI + AVD + Windows desktop gates, then release through the normal main pipeline if all checks pass.
9. Keep experimental continuous-screen collector non-canonical pending separate owner-side A/B promotion evidence.
