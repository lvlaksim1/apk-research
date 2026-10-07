# Current Blockers and Unknowns

Last reconciled: 2026-10-07.

## Release blockers

None known. v0.29.2 is published and all mandatory gates passed.

## Android home-screen shortcut

The prior experimental attempt to programmatically pin an installed Android application to Launcher3's workspace is not part of v0.29.2 and was not merged. MailRu Desktop's shortcut mechanism is a Windows Inno Setup shortcut mechanism and does not solve Android Launcher3 pinning.

If the owner still requires forced Android-home placement, treat that as a separate product feature with its own validated mechanism rather than mixing it into Windows installer work.

## WHPX

WHPX remains advisory/non-publication-gating.
