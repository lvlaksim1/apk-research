# Owner-side v0.23.1 long Continuous Screen acceptance

Date: 2026-10-07
Archive: `20261006T231833.446176Z-710dfbe4.research.zip`
Product version: 0.23.1

## Archive/session integrity

- 33/33 checksummed artifacts verified.
- Session status `complete`, `degraded=false`.
- All required and optional collectors completed.
- Continuous H.264 decodes end-to-end with ffmpeg without decoder errors.

## Canonical screenrecord rollover

Canonical Android `screenrecord` produced two chunks:
- chunk 1: 2,805 frames, first frame 23:18:36.458612Z, last frame 23:21:26.281798Z, presentation span 169.823186 s;
- chunk 2: 1,691 frames, first frame 23:21:28.247645Z, last frame 23:22:56.014823Z, presentation span 87.767178 s.

The canonical frame gap across the chunk rollover is 1.965848 s.

## Continuous Screen rollover evidence

Continuous Screen remained one collector and one monotonically advancing media stream:
- status `completed`;
- 6,970 media frames;
- 6,972 packets including codec config/EOS;
- presentation span 256.466399 s;
- clean protocol stop and cleanup;
- no receiver error.

Inside the 1.965848 s interval where canonical screenrecord has no frame, Continuous Screen contains 66 media frames. The largest adjacent Continuous Screen PTS gap within that interval is 0.100000 s.

Owner action `action-000166` occurred entirely inside the canonical rollover gap:
- target-estimated action start: 23:21:27.058248Z;
- target-estimated finish: 23:21:27.193050Z.

Continuous Screen has a media frame approximately 2.179 ms after the estimated action start and further frames throughout the action interval. This directly demonstrates useful screen evidence during a canonical chunk-rotation blind interval.

Visual inspection of the last canonical frame before rollover, Continuous Screen around action 166, and the first canonical frame after rollover confirms coherent application progression rather than a stalled/repeated stream.

## Sidecar network isolation

Archived dynamic Sidecar ports are 54420 (control) and 54430 (media).

Normalized evidence reports:
- RAW/source packets: 105,951;
- Sidecar infrastructure packets preserved in RAW: 93,556;
- Sidecar infrastructure bytes: 65,433,681;
- ordinary normalized app/network flows: 82;
- ordinary flow packets: 12,382;
- non-TCP/UDP packets: 13.

Exact Sidecar-port lookup finds zero Sidecar flows in the 82 normalized ordinary flows. Infrastructure traffic remains accounted separately.

## Quality boundary discovered during final comparison

The experimental Sidecar stream is requested at 540×960 / 2,000,000 bit/s. Canonical screenrecord is 1080×1920 and configured at 20,000,000 bit/s.

Therefore long-session continuity, rollover coverage, timing monotonicity, clean completion and derived-network isolation are proven, but the present Sidecar configuration is not resolution-equivalent to canonical screenrecord. Replacing the canonical high-resolution source outright would silently reduce spatial evidence detail by 2× per dimension (4× fewer pixels).

## Manager conclusion

The Continuous Screen mechanism itself has passed the previously open technical validation gates:
- idle survival/resume;
- long-session operation;
- canonical chunk-rollover continuity;
- clean completion;
- timestamp continuity;
- Sidecar traffic isolation from ordinary derived network evidence.

It is technically ready to leave purely experimental status as a stable continuity source.

It is not yet justified as the sole canonical replacement for high-resolution screenrecord under the current 540×960 configuration. An owner decision is required for product role. Recommended bounded options are:
1. promote Continuous Screen to a stable continuous/timeline source while retaining 1080×1920 screenrecord as canonical high-resolution evidence; or
2. first raise Continuous Screen capture quality to forensic-resolution parity and revalidate resource/storage impact before replacing canonical screenrecord.

## Authority

- source: owner-provided Research ZIP `20261006T231833.446176Z-710dfbe4.research.zip`, direct archive/PTS/video/network analysis 2026-10-07
- authority: owner-evidence + verified-archive-analysis
