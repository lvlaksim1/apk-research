# apk-research v0.27.0 — APK/XAPK Package Intake

v0.27.0 adds first-class XAPK input while preserving the verified Android runtime, research capture path and evidence semantics.

## APK/XAPK selection

- The desktop file picker accepts both `.apk` and `.xapk`.
- Single APK files keep the established `adb install -r -t -g` installation path.
- XAPK files are treated as ZIP containers and only APK/OBB payloads are materialized.

## XAPK validation and split installation

- Every APK part is inspected independently with `aapt2 dump badging`.
- All APK parts must have the same package name and compatible versionCode.
- Exactly one base APK without a split name is required.
- Duplicate split names and mixed-package containers are rejected.
- Multi-APK XAPK packages are installed atomically with `adb install-multiple -r -t -g`, with the base APK first.

## OBB payloads

- OBB files are copied only after successful APK installation.
- The destination is derived from the verified package name: `/sdcard/Android/obb/<package>/`.
- OBB transfer failures stop package preparation rather than silently starting research with incomplete assets.

## Container safety

- Rejects absolute paths and path traversal entries.
- Rejects encrypted ZIP members.
- Applies bounded APK/OBB counts and extracted-size limits.
- Rejects damaged/non-ZIP XAPK input.
- Temporary extraction is removed after installation or failure.

## Compatibility

- Hidden Emulator → gRPC/MMAP → AndroidView is unchanged.
- v0.10.5 startup/clean-launch sequencing is unchanged.
- Research ZIP schemas, RAW PCAP authority, evidence attribution and non-causality boundaries are unchanged.
- The accepted dual-source screen model is unchanged.
