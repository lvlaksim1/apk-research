# Current Project State

Last reconciled: 2026-10-08.

## Product

- Current release/main commit: `0f9d949e5158860a51d4e83624fa1cbf3db121cc`.
- Latest release: `v0.29.2`.
- Full installer: `apk-research-setup_v0.29.2.exe`.
- Update installer: `apk-research-update_v0.29.2.exe`.
- Setup SHA-256: `6acc5b72337faa92cfd930ed88151445fb218eb580b54eb4e5f65112b457c1f0`.
- Update SHA-256: `812382bbf61613f296e011c4fead9d5ede00bab9fb44679c76a6b27a542d4821`.
- Latest release target verified live on 2026-10-08: exact main SHA above.

## v0.29.2

The Windows packaging/update path matches MailRu Desktop structurally: distinct Setup and Update installers, direct Windows-shell launch of Update, same AppId, fixed per-user install directory, and Inno-owned Windows shortcut recreation.

SHA-256 verification remains mandatory and validates both published installers.

The explicit Android Home button is removed.

## Verification

PR #24 is merged at the exact baseline SHA and main pipeline #141 passed:
- full CI;
- real AVD acceptance;
- Windows standalone and GUI smoke;
- full + update installer build;
- real v0.29.1 → v0.29.2 dedicated update acceptance;
- clean-Windows Android provisioning;
- GitHub Release publication.

## Owner cancellation

On 2026-10-08 the owner explicitly cancelled the previously open requirement to place installed APK/XAPK applications as shortcuts on the managed Android home screen.

That work is no longer active and is not a blocker.

## Active development direction

The owner clarified that the next required product capability is display of decrypted HTTPS traffic inside apk-research.

The target is actual HTTP transaction content where decryption succeeds: URL, method/status, headers and request/response bodies. Existing TLS/QUIC metadata from passive PCAP analysis does not satisfy this requirement.

Passive RAW PCAP remains an independent source of truth. HTTPS interception is an active research technique and its use/effects must be recorded explicitly.

Certificate pinning/custom trust and HTTP/3/QUIC are separate capability tiers and must not be overclaimed.

## Development status

v0.29.2 is the verified baseline. HTTPS traffic inspection is the active next product stage.
