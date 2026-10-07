from __future__ import annotations

from pathlib import Path


path = Path("src/apk_research/desktop/protocol_analysis_v025.py")
text = path.read_text(encoding="utf-8")

old_dns = '''    @staticmethod
    def _dns_transactions(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for packet in packets:
            dns = packet.get("dns_message")
            if isinstance(dns, dict):
                groups[int(dns.get("id") or 0)].append(packet)
        transactions: list[dict[str, Any]] = []
        for message_id, items in groups.items():
            queries = [item for item in items if item["dns_message"].get("kind") == "query"]
            responses = [item for item in items if item["dns_message"].get("kind") == "response"]
            if len(queries) == 1 and len(responses) == 1:
                query = queries[0]
                response = responses[0]
                questions = query["dns_message"].get("questions") or []
                transactions.append(
                    {
                        "id": message_id,
                        "status": "query-response-observed",
                        "query_packet_id": _packet_id(query),
                        "response_packet_id": _packet_id(response),
                        "query_name": (
                            str(questions[0].get("name") or "")
                            if questions
                            else ""
                        ),
                        "confidence": "HIGH",
                        "basis": "matching DNS transaction id in one selected flow",
                    }
                )
            else:
                transactions.append(
                    {
                        "id": message_id,
                        "status": "partial-or-ambiguous",
                        "query_packet_ids": [_packet_id(item) for item in queries],
                        "response_packet_ids": [_packet_id(item) for item in responses],
                        "confidence": "LOW",
                        "basis": "capture contains no unique query/response pair for this id",
                    }
                )
        return sorted(transactions, key=lambda value: int(value["id"]))
'''

new_dns = '''    @staticmethod
    def _dns_transactions(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
        positions = {id(packet): index for index, packet in enumerate(packets)}
        for packet in packets:
            dns = packet.get("dns_message")
            if isinstance(dns, dict):
                groups[int(dns.get("id") or 0)].append(packet)
        transactions: list[dict[str, Any]] = []
        for message_id, items in groups.items():
            queries = [item for item in items if item["dns_message"].get("kind") == "query"]
            responses = [item for item in items if item["dns_message"].get("kind") == "response"]
            ordered_pair = (
                len(queries) == 1
                and len(responses) == 1
                and positions[id(queries[0])] < positions[id(responses[0])]
            )
            if ordered_pair:
                query = queries[0]
                response = responses[0]
                questions = query["dns_message"].get("questions") or []
                transactions.append(
                    {
                        "id": message_id,
                        "status": "query-response-observed",
                        "query_packet_id": _packet_id(query),
                        "response_packet_id": _packet_id(response),
                        "query_name": (
                            str(questions[0].get("name") or "")
                            if questions
                            else ""
                        ),
                        "confidence": "HIGH",
                        "basis": "matching DNS transaction id with query-before-response capture order in one selected flow",
                    }
                )
            else:
                transactions.append(
                    {
                        "id": message_id,
                        "status": "partial-or-ambiguous",
                        "query_packet_ids": [_packet_id(item) for item in queries],
                        "response_packet_ids": [_packet_id(item) for item in responses],
                        "confidence": "LOW",
                        "basis": "capture contains no unique capture-ordered query/response pair for this id",
                    }
                )
        return sorted(transactions, key=lambda value: int(value["id"]))
'''

old_http = '''    @staticmethod
    def _http_transactions(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        requests = [
            packet
            for packet in packets
            if isinstance(packet.get("http_metadata"), dict)
            and packet["http_metadata"].get("kind") == "request"
        ]
        responses = [
            packet
            for packet in packets
            if isinstance(packet.get("http_metadata"), dict)
            and packet["http_metadata"].get("kind") == "response"
        ]
        if len(requests) != 1 or len(responses) != 1:
            return []
        request = requests[0]
        response = responses[0]
        if _direction(request) == _direction(response):
            return []
        return [
            {
                "status": "single-unambiguous-observed-pair",
                "request_packet_id": _packet_id(request),
                "response_packet_id": _packet_id(response),
                "method": request["http_metadata"].get("method"),
                "target": request["http_metadata"].get("target"),
                "status_code": response["http_metadata"].get("status"),
                "confidence": "HIGH",
                "basis": "exactly one complete cleartext request and one complete cleartext response in opposite directions",
            }
        ]
'''

new_http = '''    @staticmethod
    def _http_transactions(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        positions = {id(packet): index for index, packet in enumerate(packets)}
        requests = [
            packet
            for packet in packets
            if isinstance(packet.get("http_metadata"), dict)
            and packet["http_metadata"].get("kind") == "request"
        ]
        responses = [
            packet
            for packet in packets
            if isinstance(packet.get("http_metadata"), dict)
            and packet["http_metadata"].get("kind") == "response"
        ]
        if len(requests) != 1 or len(responses) != 1:
            return []
        request = requests[0]
        response = responses[0]
        if (
            _direction(request) == _direction(response)
            or positions[id(request)] >= positions[id(response)]
        ):
            return []
        return [
            {
                "status": "single-unambiguous-observed-pair",
                "request_packet_id": _packet_id(request),
                "response_packet_id": _packet_id(response),
                "method": request["http_metadata"].get("method"),
                "target": request["http_metadata"].get("target"),
                "status_code": response["http_metadata"].get("status"),
                "confidence": "HIGH",
                "basis": "exactly one complete cleartext request-before-response pair in opposite directions",
            }
        ]
'''

if old_dns not in text:
    raise SystemExit("DNS pairing block not found")
if old_http not in text:
    raise SystemExit("HTTP pairing block not found")

path.write_text(
    text.replace(old_dns, new_dns, 1).replace(old_http, new_http, 1),
    encoding="utf-8",
    newline="\n",
)
