# Manager intentions and commitments

## Completed — v0.29.2 MailRu-style installer model
Status: completed and released.

Owner direction: inspect the working update installer and application shortcut implementation in `lvlaksim1/mailru-desktop` and make apk-research use the same Windows installation/update approach.

Delivered:
- dedicated full Setup installer;
- dedicated Update installer;
- latest-release discovery selects only Update;
- SHA-256 verification retained;
- direct Windows-shell launch of Update followed by application exit;
- Inno-owned Start-menu/optional desktop shortcut creation and refresh;
- no uninstall-first behavior;
- redundant Android Home button removed;
- GitHub Release contains Setup + Update + SHA256SUMS.

Completion evidence: PR #24 and main pipeline #141 passed mandatory CI/AVD/Windows/release gates.

## Cancelled — Android home-screen shortcut after APK/XAPK install
Status: cancelled by owner on 2026-10-08.

The owner explicitly withdrew the requirement to place the installed APK/XAPK application on the managed Android home screen.

Consequences:
- this is no longer an active commitment or blocker;
- do not resume the prior Launcher3 shortcut experiments;
- do not merge the old experimental branch as-is;
- the removed separate Android Home button remains removed unless explicitly requested otherwise.

## Active — decrypted HTTPS traffic display
Status: active owner requirement.

Required behavior:
- apk-research must display decrypted HTTPS application traffic, not merely TLS/QUIC metadata;
- show HTTP request and response details including URL, method/status, headers and body where captured;
- keep passive RAW PCAP authoritative and separate from active interception evidence;
- clearly record when interception/proxy/certificate handling may alter application network behavior;
- treat certificate-pinned/custom-trust applications as a separate capability tier rather than claiming universal decryption prematurely.

## Active — continuity and release integrity
Status: active.

Reconcile live product/release/CI before consequential changes and preserve all verified evidence/runtime boundaries.
