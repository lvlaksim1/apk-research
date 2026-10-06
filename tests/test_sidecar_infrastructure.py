from __future__ import annotations

import json

from apk_research.timeline_engine import (
    _mark_sidecar_infrastructure,
    _sidecar_infrastructure_ports,
)


def test_sidecar_infrastructure_uses_exact_archived_loopback_ports(
    tmp_path,
) -> None:
    metadata = tmp_path / "02_normalized" / "continuous-screen.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(
        json.dumps(
            {
                "sidecar_handshake": {
                    "host_port": 63564,
                    "device_port": 63564,
                },
                "stream": {
                    "host_port": 63576,
                    "device_port": 63576,
                },
            }
        ),
        encoding="utf-8",
    )

    ports = _sidecar_infrastructure_ports(tmp_path)
    assert ports == {63564, 63576}

    packets = [
        {
            "protocol": "tcp",
            "src": "127.0.0.1",
            "src_port": 47032,
            "dst": "127.0.0.1",
            "dst_port": 63564,
            "captured_length": 100,
        },
        {
            "protocol": "tcp",
            "src": "127.0.0.1",
            "src_port": 63576,
            "dst": "127.0.0.1",
            "dst_port": 36780,
            "captured_length": 200,
        },
        {
            "protocol": "tcp",
            "src": "127.0.0.1",
            "src_port": 11111,
            "dst": "127.0.0.1",
            "dst_port": 22222,
            "captured_length": 300,
        },
        {
            "protocol": "tcp",
            "src": "10.0.2.15",
            "src_port": 40000,
            "dst": "93.184.216.34",
            "dst_port": 443,
            "captured_length": 400,
        },
    ]

    result = _mark_sidecar_infrastructure(
        packets,
        ports,
    )

    assert result == {
        "packet_count": 2,
        "captured_bytes": 300,
    }
    assert packets[0]["infrastructure"]["kind"] == "apk-research-sidecar"
    assert packets[1]["infrastructure"]["kind"] == "apk-research-sidecar"
    assert "infrastructure" not in packets[2]
    assert "infrastructure" not in packets[3]
