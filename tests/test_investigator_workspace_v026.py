from __future__ import annotations

from apk_research.desktop.investigator_workspace_v026 import (
    active_evidence_refs,
    add_evidence_set,
    build_report_data,
    build_workspace_model,
    empty_workspace_state,
    filter_workspace_rows,
    normalize_workspace_state,
    report_markdown,
    set_evidence_membership,
    toggle_bookmark,
    workspace_state_path,
)


def _model():
    flow_one = {
        "flow_id": "flow-1",
        "protocol": "tcp",
        "remote_ip": "203.0.113.10",
        "remote_port": 443,
        "application_protocols": ["TLS"],
        "tls_sni": ["api.example.test"],
        "owner": {
            "processes": ["com.example.app"],
            "pids": [1234],
            "inode": 77,
            "confidence": "HIGH",
        },
    }
    flow_two = {
        "flow_id": "flow-2",
        "protocol": "udp",
        "remote_ip": "198.51.100.53",
        "remote_port": 53,
        "application_protocols": ["DNS"],
        "dns_queries": ["example.test"],
        "owner": {
            "processes": ["com.example.app"],
            "pids": [1234],
            "inode": 88,
            "confidence": "HIGH",
        },
    }
    return {
        "package": "com.example.app",
        "action_count": 1,
        "flow_count": 2,
        "rows": [
            {
                "sequence": 0,
                "kind": "user_action",
                "name": "tap",
                "target_utc": "2026-10-07T01:00:00Z",
                "host_utc": "2026-10-07T01:00:00Z",
                "action_id": "action-0001",
                "flow_ids": ["flow-1"],
                "flows": [flow_one],
                "packet_count": 8,
                "relation_type": "temporal-only",
                "relation_strength": "bounded",
                "causal_claim": False,
                "screen": {"continuous": {"sequence": 10}},
            },
            {
                "sequence": 1,
                "kind": "network_flow",
                "name": "dns-flow",
                "target_utc": "2026-10-07T01:00:03Z",
                "host_utc": "2026-10-07T01:00:03Z",
                "action_id": "",
                "flow_ids": ["flow-2"],
                "flows": [flow_two],
                "packet_count": 2,
                "relation_type": "observed-normalized-flow",
                "relation_strength": "direct-observation",
                "causal_claim": False,
                "screen": {},
            },
        ],
    }


def test_workspace_builds_stable_refs_and_search_facets():
    first = build_workspace_model(_model())
    second = build_workspace_model(_model())

    assert first["row_count"] == 2
    assert first["package"] == "com.example.app"
    assert first["rows"][0]["ref"].startswith("EV-")
    assert first["rows"][0]["ref"] == second["rows"][0]["ref"]
    assert first["rows"][0]["evidence_class"] == "temporal-relationship"
    assert first["rows"][1]["evidence_class"] == "observed-fact"
    assert "TLS" in first["protocols"]
    assert "DNS" in first["protocols"]
    assert "203.0.113.10:443" in first["endpoints"]
    assert "com.example.app" in first["processes"]


def test_workspace_filters_are_intersections_not_inferences():
    model = build_workspace_model(_model())

    tls_rows = filter_workspace_rows(
        model,
        query="api.example.test action-0001",
        protocol="TLS",
        process="com.example.app",
        endpoint="203.0.113.10",
    )
    assert [row["action_id"] for row in tls_rows] == ["action-0001"]

    later = filter_workspace_rows(
        model,
        start_utc="2026-10-07T01:00:02Z",
        protocol="DNS",
    )
    assert [row["name"] for row in later] == ["dns-flow"]

    assert filter_workspace_rows(model, protocol="HTTP") == []


def test_workspace_state_sets_and_bookmarks_are_bounded_to_valid_refs():
    model = build_workspace_model(_model())
    refs = [row["ref"] for row in model["rows"]]
    state = empty_workspace_state("sample.research.zip")

    assert toggle_bookmark(state, refs[0]) is True
    assert refs[0] in state["bookmarks"]
    assert toggle_bookmark(state, refs[0]) is False
    assert refs[0] not in state["bookmarks"]

    set_id = add_evidence_set(state, "API evidence")
    set_evidence_membership(state, set_id, refs, include=True)
    assert active_evidence_refs(state) == sorted(refs, key=str.lower)

    state["bookmarks"] = [refs[0], "EV-DOES-NOT-EXIST"]
    state["evidence_sets"][-1]["refs"].append("EV-DOES-NOT-EXIST")
    normalized = normalize_workspace_state(
        state,
        archive="sample.research.zip",
        valid_refs=refs,
    )
    assert "EV-DOES-NOT-EXIST" not in normalized["bookmarks"]
    assert "EV-DOES-NOT-EXIST" not in normalized["evidence_sets"][-1]["refs"]


def test_report_keeps_navigation_refs_and_no_causal_upgrade():
    model = build_workspace_model(_model())
    refs = [row["ref"] for row in model["rows"]]
    report = build_report_data(
        model,
        refs,
        archive="sample.research.zip",
        title="Case notes",
    )
    markdown = report_markdown(report)

    assert report["item_count"] == 2
    assert report["items"][0]["source_navigation"]["workspace_ref"] in refs
    assert all(item["causal_claim"] is False for item in report["items"])
    assert refs[0] in markdown
    assert "RAW evidence remains authoritative" in markdown
    assert "do not establish causality" in markdown


def test_workspace_state_is_external_to_research_zip():
    path = workspace_state_path("C:/research/sample.research.zip")
    assert path.name == "sample.research.zip.investigator.json"
