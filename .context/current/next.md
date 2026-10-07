# Next Actions

1. Treat v0.25.0 / `3717210a9db3074569602afc336380fd26598dd7` as the verified release baseline.
2. Create a dedicated v0.26 Investigator Workspace feature branch from current `main`.
3. Reuse Session Evidence, Evidence Explorer and Packet Inspector as the authoritative derived views; do not duplicate capture or protocol parsers.
4. Implement behavior/session overview, global search/filters, bookmarks/evidence sets, report generation and reverse evidence navigation.
5. Keep relation labels explicit and preserve RAW authority, temporal-only action/network semantics and unchanged attribution confidence.
6. Run focused tests plus full CI, real AVD Research ZIP acceptance and Windows installer/smoke gates before release.
7. Preserve hidden Emulator → gRPC/MMAP → AndroidView and v0.10.5 startup/clean-launch sequencing.
8. Keep Audio Evidence and user-facing Virtual Display out of scope.
