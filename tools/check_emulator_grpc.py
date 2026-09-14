from __future__ import annotations

import argparse
import json

from mobile_research.desktop.emulator_grpc import (
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
            width=360,
            height=640,
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

        client.tap(
            frame.input_width // 2,
            min(
                frame.input_height - 1,
                100,
            ),
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
