# Latest Handoff

Generation: 6
Date: 2026-10-06

Persistent manager: `apk-research-project-manager`.

Authority:
- manager state: `context`;
- product: `main`.

Verified release baseline is **apk-research v0.22.0** at `d58265584223246974fb641f02e0dd3fb8d3f4f1`. Main pipeline #125 completed SUCCESS and GitHub Release v0.22.0 is published.

Active development is **v0.23 Transport Session Evidence** on `dev-v023-transport-session`, HEAD `654e32d2c857af7ddf0de82594ef90dd34aba3a8`, 5 commits ahead of main and 0 behind.

Current v0.23 HEAD has green CI (#257), real AVD Acceptance (#93) and Desktop Build (#178). It adds TCP sequence/ack/flags/window/payload evidence plus conservative handshake/termination summaries derived only from packets present in raw PCAP. Missing lifecycle packets remain explicitly `not observed in capture`.

An earlier test expectation failed and was corrected; current verification is green. v0.23 is not yet in main and has not been published.

Stages A-D and v0.22 Stage E increment 1 are released. Continuous-screen evidence remains experimental; canonical screenrecord remains unchanged. Audio Evidence and Virtual Display remain excluded.
