# apk-research v0.20.0

v0.20.0 adds **Continuous Screen Evidence** as an experimental A/B capture path on top of the v0.19 Android Sidecar Foundation.

## Added

- sidecar protocol v2 / agent 0.2.0;
- a dedicated binary media socket isolated from the sidecar control channel;
- host-listen-first `adb reverse` setup for the media channel;
- Android Surface/MediaCodec H.264 screen capture from display 0;
- exact MediaCodec packet payload preservation;
- device-generated packet PTS, codec-config/key-frame/EOS flags and raw byte offsets;
- `01_raw/screen/continuous-screen.h264`;
- `02_normalized/continuous-screen-packets.jsonl`;
- `02_normalized/continuous-screen.json`;
- `02_normalized/screen-ab-comparison.json`;
- real-AVD acceptance for packet/byte accounting, monotonic media PTS, codec config, terminal EOS and sidecar cleanup.

## Evidence boundary

Android `screenrecord` remains the canonical required screen collector. The sidecar collector is experimental and non-required, so a sidecar-specific failure does not degrade otherwise valid canonical evidence.

The A/B report explicitly records `promotion_decision=not-automatic`. A future promotion requires real owner-side Research ZIP evidence; v0.20 does not infer equivalence from CI alone.

MediaCodec PTS remain in the device media-presentation clock domain. They are preserved exactly and are not mislabeled as UTC.

## Unchanged

- hidden Emulator → gRPC/MMAP → AndroidView live display;
- persistent Emulator gRPC input;
- v0.10.5 startup/clean-launch sequencing;
- canonical Android screenrecord evidence;
- raw PCAP and package/socket attribution semantics;
- Action ↔ Flow `temporal-only` / `causal_claim=false` semantics.

Audio Evidence and the user-facing Virtual Display research mode remain out of scope.

## Validation

Stable publication requires normal CI, real AVD Research ZIP acceptance including the continuous-screen gate, Windows standalone/GUI/installer smoke, clean-Windows provisioning and checksum verification.
