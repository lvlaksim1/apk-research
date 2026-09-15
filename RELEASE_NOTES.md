# Mobile Research v0.8.7

v0.8.7 fixes the startup sequencing regression found during the first real-PC test of the v0.8.6 fail-fast runtime.

## Problem reproduced

v0.8.6 started the gRPC/MMAP framebuffer worker immediately after the Emulator gRPC endpoint became ready and also synchronously required the first frame within 15 seconds.

On the real Windows machine, gRPC was ready before Android's graphics/compositor path produced the first frame. Mobile Research therefore reported:

`Обязательный gRPC/MMAP framebuffer не выдал первый кадр за 15 секунд`

The framebuffer worker itself remained alive, and the same gRPC/MMAP stream later produced the Android image. However, the preparation worker had already aborted, so root, PCAP readiness and APK installation were not completed.

## Fix

The two concerns are now separated:

1. the framebuffer worker starts immediately after gRPC becomes ready so boot frames may appear early;
2. this early start is non-blocking;
3. Android continues normal boot and root preparation;
4. after `ensure_ready` finishes, Mobile Research requires the first real `grpc-mmap` frame;
5. only a failure at that point is treated as a required-transport error.

No compatibility or fallback mode has been reintroduced.

## Preserved architecture

Windows remains:

`-qt-hide-window → gRPC → MMAP → AndroidView`

Input remains:

`AndroidView → persistent gRPC streamInputEvent → Android`

Private-AVD cleanup and one-shot `-wipe-data` recovery remain unchanged.
