# Mobile Research v0.2.2

Hotfix for Windows hypervisor compatibility discovered during real-user testing of v0.2.1.

## Fixed

On a Windows 10 machine with **AEHD 2.2 already installed and usable**, v0.2.1 incorrectly rejected Android Emulator because it required WHPX at runtime. It then attempted to enable two Windows features separately, producing two UAC prompts, and immediately rechecked acceleration before a reboot could activate the Windows hypervisor.

v0.2.2 fixes that behavior:

- **WHPX remains the preferred Windows hypervisor.**
- An already-installed and usable **AEHD/GVM is accepted as a compatible transition fallback** and no longer blocks Mobile Research.
- A usable AEHD system does **not** trigger UAC and does **not** require an immediate reboot.
- Automatic Windows hypervisor setup runs only when Android Emulator reports no usable hypervisor at all.
- Windows setup now uses **one UAC prompt**, not two.
- Mobile Research enables only `HypervisorPlatform`; it no longer enables unrelated `VirtualMachinePlatform`.
- The setup also ensures `hypervisorlaunchtype=Auto`.
- If Windows configuration genuinely requires a reboot, Mobile Research explicitly tells the user that a reboot is required, even when Windows itself does not show a restart prompt.

## Preserved from v0.2.1

The real-application `com.evrasia` package-metadata fix remains in place:

- bounded Package Manager metadata collection;
- fallback package dump path;
- a failed full package dump degrades the session instead of destroying the entire research run;
- logcat, screen recording and raw PCAP can continue;
- degraded evidence resolves to `partial`, not falsely `complete`.

## Validation

The development hotfix passed:

- Windows CI;
- unit tests including explicit AEHD/WHPX compatibility cases;
- standalone EXE build;
- standalone self-test;
- GUI smoke-test;
- Inno Setup build;
- installed-application smoke-test;
- clean Windows managed-Android provisioning.

The normal release commit is revalidated again by CI, Desktop Build and real Android/KVM acceptance before publication.

## Distribution

Release assets:

- `MobileResearchSetup.exe`
- `SHA256SUMS.txt`

Normal use requires no separately installed Python, Android Studio or ADB.
