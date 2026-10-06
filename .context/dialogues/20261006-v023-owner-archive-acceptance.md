# Owner-side v0.23 real Research ZIP acceptance

Date: 2026-10-06
Archive: `20261006T105244.785342Z-3076e6ba.research.zip`
Product version: 0.23.0

## Healthy evidence

- 31/31 checksummed archive artifacts verified.
- Session status `complete`, `degraded=false`.
- Target: `com.evrasia` 2.8.4, Android 15 / API 35.
- Clean launch reports `LaunchState: COLD`.
- Canonical screenrecord: 1080×1920 H.264, 918 frames, 66.104 s presentation span; visually covers Launcher → cold launch → app interaction → final profile screen.
- tcpdump: 12,429 packets captured, 0 packets dropped by kernel.
- Network inventory packet accounting matches source PCAP: 12,419 TCP/UDP + 10 non-TCP/UDP = 12,429.
- Socket attribution: 75 snapshots, unique target UID 10148, 214 PID/socket links; major target HTTPS flows are EXACT-attributed.
- No FATAL EXCEPTION, ANR or target process crash found for com.evrasia.
- v0.23 TCP evidence is present: most target HTTPS flows show complete SYN → SYN/ACK → ACK; several evrasia.spb.ru flows also show FIN termination.

## Defect 1 — sidecar traffic contaminates normalized network evidence

Two loopback flows are apk-research infrastructure:
- control: 127.0.0.1:63564 ↔ 127.0.0.1:47032, 23 packets;
- media: 127.0.0.1:63576 ↔ 127.0.0.1:36780, 11,970 packets.

Together:
- 11,993 / 12,419 TCP/UDP flow packets = 96.57%;
- 7,208,463 / 7,396,346 TCP/UDP flow bytes = 97.46%.

The media flow is correlated with 15 of 16 user actions. This is researcher-induced infrastructure traffic and must not appear as ordinary application network evidence. Raw PCAP itself is valid and should stay untouched.

After removing these infrastructure flows, the session contains 27 genuine/non-sidecar flows, 426 TCP/UDP packets and 187,883 TCP/UDP captured bytes. Observed hosts include evrasia.spb.ru, proxy.mob.maps.yandex.net, Firebase Remote Config/logging, time.google.com and mDNS/NTP traffic.

## Defect 2 — continuous-screen idle timeout

`continuous-screen.json`:
- status: `failed-experimental`;
- packet_count: 157;
- media_frame_count: 156;
- captured bytes: 1,171,247;
- presentation span: 10.041769 s;
- receiver error: `Unable to read Android sidecar media stream`;
- no clean SCREEN_STOP statistics;
- cleanup incomplete.

Implementation/evidence match:
- host `AndroidSidecar(timeout=8.0)` applies the same 8 s timeout to the accepted media connection;
- `ScreenStreamer` requests `KEY_REPEAT_PREVIOUS_FRAME_AFTER=100000`;
- real logcat for the sidecar encoder states `no c2 equivalents for repeat-previous-frame-after`;
- last media PTS maps to approximately 10:53:01.030Z;
- first subsequent user action starts at target-estimated 10:53:09.655Z;
- idle gap = 8.624 s > 8 s media socket timeout.

Therefore a legitimate static-screen interval can terminate the host receiver. The continuous collector must remain experimental/non-canonical.

## Canonical conclusion

The main v0.23 research chain is usable and evidence-complete because required collectors remain healthy and canonical screenrecord works. The experimental continuous-screen path must not be promoted and should be corrected or disabled before further reliance.
