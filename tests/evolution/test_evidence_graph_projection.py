# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from runtime.evolution.evidence_graph import build_evidence_graph_projection
from runtime.evolution.lineage_v2 import LineageLedgerV2


def test_evidence_graph_projection_builds_mutation_and_evidence_nodes(tmp_path) -> None:
    ledger = LineageLedgerV2(tmp_path / "lineage_graph.jsonl")
    epoch_id = "epoch-graph-1"
    ledger.append_event("MutationBundleEvent", {"epoch_id": epoch_id, "bundle_id": "mut-1"})
    ledger.append_event(
        "MutationEvidenceEvent",
        {
            "epoch_id": epoch_id,
            "mutation_id": "mut-1",
            "evidence_id": "evidence-mut-1",
            "evidence_status": "valid",
            "evidence_bundle_id": "mut-1",
            "evidence_bundle_valid": True,
        },
    )

    projection = build_evidence_graph_projection(ledger, epoch_id=epoch_id, limit=50)
    assert projection["ok"] is True
    assert projection["epoch_id"] == epoch_id
    assert projection["node_count"] >= 2
    assert projection["edge_count"] >= 1
    node_ids = {node["id"] for node in projection["nodes"]}
    assert "mutation:mut-1" in node_ids
    assert "evidence:evidence-mut-1" in node_ids


def test_evidence_graph_projection_is_deterministic(tmp_path) -> None:
    ledger = LineageLedgerV2(tmp_path / "lineage_graph_deterministic.jsonl")
    epoch_id = "epoch-graph-2"
    ledger.append_event("MutationBundleEvent", {"epoch_id": epoch_id, "bundle_id": "mut-2"})
    ledger.append_event(
        "MutationEvidenceEvent",
        {
            "epoch_id": epoch_id,
            "mutation_id": "mut-2",
            "evidence_id": "evidence-mut-2",
            "evidence_status": "pending",
            "evidence_bundle_id": "",
            "evidence_bundle_valid": False,
        },
    )

    first = build_evidence_graph_projection(ledger, epoch_id=epoch_id, limit=50)
    second = build_evidence_graph_projection(ledger, epoch_id=epoch_id, limit=50)
    assert first == second
