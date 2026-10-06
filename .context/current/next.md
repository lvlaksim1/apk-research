# Next Actions

1. Treat v0.23.1 / `39e483ee03d5337e4e928b4b85cce85c40f4fe35` as the verified release baseline and owner-revalidated correction for the v0.23.0 Sidecar defects.
2. Ask the owner for one final Continuous Screen A/B session of about four minutes so canonical `screenrecord` crosses its 170 s chunk boundary.
3. During that run, ensure ordinary interaction occurs around the rollover; a long static pause is no longer required because the 59 s idle-resume case is already proven.
4. Verify continuity, timing and visual equivalence around the chunk transition; re-check RAW Sidecar preservation/exclusion and clean collector completion.
5. If the long-session gate passes, present an explicit recommendation whether to promote Continuous Screen from experimental/non-canonical status.
6. Preserve hidden Emulator → gRPC/MMAP → AndroidView and v0.10.5 startup/clean-launch sequencing.
7. After the screen decision, continue Stage E from the smallest high-value remaining evidence/navigation gap.
8. Keep Audio Evidence and user-facing Virtual Display out of scope.
