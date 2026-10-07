# Manager intentions and commitments

## Completed — v0.29.2 MailRu-style installer model
Status: completed and released.

Owner direction: inspect the working update installer and application shortcut implementation in `lvlaksim1/mailru-desktop` and make apk-research work the same way.

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

## Active — continuity and release integrity
Status: active.

No later product stage is active unless the owner defines it.
