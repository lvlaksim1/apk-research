# Project Goals

## Current durable goals

- Provide a normal standalone Windows application rather than a CLI-oriented research wrapper.
- Manage the required Android Emulator/runtime automatically so the owner does not need to install Python or manually assemble the runtime.
- Capture reproducible forensic evidence in a Research ZIP and keep raw evidence distinct from derived analysis.
- Attribute network activity to the researched Android package as strongly as available evidence permits.
- Provide useful post-capture analysis through Timeline, Network Analyzer and Unified Evidence Explorer.
- Support modern network protocols without overclaiming what encrypted traffic proves.
- Keep installation/update handoff simple through versioned Windows installers and reproducible GitHub releases.
- Continue development incrementally from verified baselines while avoiding regressions in the established Android runtime path.

## Definition of done for release-bound work

A release-bound change is done only after the applicable repository test suite and main pipeline gates succeed, including real AVD acceptance and Windows packaging/provisioning where configured, and the resulting release asset is tied to the exact release commit.
