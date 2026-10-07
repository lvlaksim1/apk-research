# Manager beliefs

## Verified baseline

Current product baseline is **apk-research v0.29.2** at `0f9d949e5158860a51d4e83624fa1cbf3db121cc`.

Live reconciliation on 2026-10-08 confirmed that `main`, PR #24 merge commit and the latest GitHub Release all point to that exact SHA.

Published assets:
- `apk-research-setup_v0.29.2.exe` — 36,477,159 bytes — SHA-256 `6acc5b72337faa92cfd930ed88151445fb218eb580b54eb4e5f65112b457c1f0`;
- `apk-research-update_v0.29.2.exe` — 36,477,534 bytes — SHA-256 `812382bbf61613f296e011c4fead9d5ede00bab9fb44679c76a6b27a542d4821`;
- `SHA256SUMS.txt` covers both installers.

Main pipeline #141 passed all mandatory release gates and published v0.29.2.

## Windows installer/update architecture

v0.29.2 adopts the MailRu Desktop architecture. Setup and Update are separate Inno Setup packages with one AppId and a fixed per-user install directory. The application resolves only the Update asset from the latest stable GitHub Release, verifies SHA-256, launches it through the Windows shell and exits. Inno Setup owns the update wizard and Windows shortcut recreation.

The update package does not invoke the old uninstaller. Start-menu and optional desktop shortcuts are recreated by Inno Setup on update so icon/metadata refresh naturally.

## Android installation UX

The redundant «Открыть главный экран Android» button is removed and must not be reintroduced.

The previously open owner requirement to create an Android home-screen shortcut after APK/XAPK installation was explicitly cancelled by the owner on 2026-10-08. It is not an active product requirement and must not be resumed unless the owner explicitly reopens it.

Prior Launcher3 provider/database experiments remain research history only and were never merged into the verified product.

## Protected product semantics

APK/XAPK handling, hidden Emulator → gRPC/MMAP → AndroidView, v0.10.5 startup sequencing, Research ZIP, RAW PCAP authority, evidence semantics and the accepted dual-source screen model remain unchanged.
