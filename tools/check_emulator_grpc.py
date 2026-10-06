from __future__ import annotations

import argparse
import json

from apk_research.desktop.emulator_grpc import (
    EmulatorGrpcClient,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port",
        type=int,
        default=8554,
    )
    args = parser.parse_args()

    client = EmulatorGrpcClient(args.port)
    try:
        client.wait_ready(timeout=15.0)
        stream = client.stream_frames(
            width=405,
            height=720,
            timeout=15.0,
        )
        frame = next(stream)
        if (
            frame.width <= 0
            or frame.height <= 0
            or not frame.data
        ):
            raise RuntimeError(
                "gRPC screenshot was empty"
            )

        if frame.transport != "grpc-mmap":
            raise RuntimeError(
                "Expected grpc-mmap framebuffer, got "
                + frame.transport
            )

        client.tap(
            frame.input_width // 2,
            min(
                frame.input_height - 1,
                100,
            ),
        )

        center_x = frame.input_width // 2
        center_y = frame.input_height // 2
        spread_x = max(20, frame.input_width // 8)
        two_finger = (
            (
                0,
                max(0, center_x - spread_x),
                center_y,
            ),
            (
                1,
                min(
                    frame.input_width - 1,
                    center_x + spread_x,
                ),
                center_y,
            ),
        )
        client.touch_points(
            tuple(
                (identifier, x, y, 1)
                for identifier, x, y in two_finger
            )
        )
        client.touch_points(
            tuple(
                (identifier, x, y, 0)
                for identifier, x, y in two_finger
            )
        )
        client.send_key("GoHome")

        print(
            json.dumps(
                {
                    "status": "success",
                    "transport": frame.transport,
                    "width": frame.width,
                    "height": frame.height,
                    "bytes": len(frame.data),
                    "seq": frame.seq,
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
