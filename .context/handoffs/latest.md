# Latest Handoff

Generation: 30
Date: 2026-10-10
Persistent manager: apk-research-project-manager
Product authority: main
Manager-state authority: context

## Published product release

apk-research **v0.33.0**, exact main/release commit `3f3f1144e0ea8944a065e7d5950fd07fd1e17abf`. PR #31 merged; main pipeline **#146 attempt 1 SUCCESS**, including unit tests, real Android 15 research/HTTPS acceptance, standalone Windows GUI verification, full + update installers, actual v0.32.0 to v0.33.0 upgrade, clean Windows provisioning and publication.

Published assets:
- Setup `apk-research-setup_v0.33.0.exe`, SHA256 `70788ed8a2cf8885eea5beb77df1cd560ad41aaa67d49978ba9e972def114718`.
- Update `apk-research-update_v0.33.0.exe`, SHA256 `a6db937f410f03b49fbc8bff4791a93b367d905245a5b4554aaeab0adb12b38a`.
- `SHA256SUMS.txt` published.

## Owner-directed simplified UX — COMPLETE

The Windows entrypoint now uses a MainWindow with exactly two user-visible tabs: `Исследование` and `HTTPS • онлайн`. The previous inherited UI stack creating Network, Evidence, Packets, Investigator and similar tabs is no longer the default. A small Program menu retains updater/Android maintenance; Research retains APK/XAPK, Android view, start/finish controls and ZIP directory access. The Android header shows a live HTTPS count and quick navigation button.

The new HTTPS viewer incrementally reads completed JSONL records from the running session every 500 ms, shows method, host, path, HTTP status, headers and body preview, and switches to ZIP data when finished. Full body files remain in Research ZIP; preview is capped at 128 KiB for responsiveness. All mandatory collectors and archive artifacts continue unchanged.

RAW capture uses `tcpdump -B 16384 -s 0 -U`: 16-MiB kernel buffer, full packet lengths. This aims to reduce prior packet drops, not a guarantee. Next real archive should measure actual drops.

## Previously completed HTTPS field validation

The user's actual v0.32.0 `com.evrasia` ZIP from 2026-10-10 showed 32 readable HTTPS transactions (23 target domain), 21 direct route journal connections to target address, complete session and 99/99 hashes. Former direct-HTTPS gap remains verified resolved in that run. Do not misinterpret v0.33.0 as a TLS protocol change.

## Remaining constraints

Never publish owner ZIPs or authentication contents; prior private sample contained token fields. Preserve Android ARM64/XAPK, root/gRPC/MMAP, research provenance and independent RAW PCAP. Home-screen shortcut cancelled. Use neutral owner-visible language.
