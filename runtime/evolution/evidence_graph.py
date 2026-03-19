# SPDX-License-Identifier: Apache-2.0
"""Deterministic evidence-graph projection helpers for Aponi endpoints."""

from __future__ import annotations

from typing import Any, Dict, List

from runtime.evolution.lineage_v2 import LineageLedgerV2


def _mutation_id_from_payload(payload: Dict[str, Any]) -> str:
    certificate = payload.get("certificate") if isinstance(payload.get("certificate"), dict) else {}
    return str(
        payload.get("mutation_id")
        or payload.get("bundle_id")
        or certificate.get("mutation_id")
        or certificate.get("bundle_id")
        or ""
    ).strip()


def build_evidence_graph_projection(
    ledger: LineageLedgerV2,
    *,
    epoch_id: str = "",
    limit: int = 100,
) -> Dict[str, Any]:
    """Build deterministic mutation/evidence graph nodes + edges from lineage events."""
    normalized_limit = max(1, min(500, int(limit)))
    events = ledger.read_epoch(epoch_id) if epoch_id else ledger.read_all()
    events = events[-normalized_limit:]

    nodes_by_id: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, str]] = []

    for entry in events:
        if not isinstance(entry, dict):
            continue
        entry_type = str(entry.get("type") or "").strip()
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        resolved_epoch_id = str(payload.get("epoch_id") or epoch_id or "").strip()
        mutation_id = _mutation_id_from_payload(payload)
        if not mutation_id:
            continue

        mutation_node_id = f"mutation:{mutation_id}"
        if mutation_node_id not in nodes_by_id:
            nodes_by_id[mutation_node_id] = {
                "id": mutation_node_id,
                "kind": "mutation",
                "mutation_id": mutation_id,
                "epoch_id": resolved_epoch_id,
            }

        if entry_type == "MutationEvidenceEvent":
            evidence_id = str(payload.get("evidence_id") or f"{mutation_id}:evidence").strip()
            evidence_node_id = f"evidence:{evidence_id}"
            nodes_by_id[evidence_node_id] = {
                "id": evidence_node_id,
                "kind": "evidence",
                "mutation_id": mutation_id,
                "epoch_id": resolved_epoch_id,
                "status": str(payload.get("evidence_status") or ""),
                "evidence_bundle_id": str(payload.get("evidence_bundle_id") or ""),
                "evidence_bundle_valid": bool(payload.get("evidence_bundle_valid", False)),
            }
            edges.append({"from": mutation_node_id, "to": evidence_node_id, "relation": "supported_by"})

        parent_mutation_id = str(payload.get("parent_mutation_id") or payload.get("parent_bundle_id") or "").strip()
        if parent_mutation_id:
            parent_node_id = f"mutation:{parent_mutation_id}"
            if parent_node_id not in nodes_by_id:
                nodes_by_id[parent_node_id] = {
                    "id": parent_node_id,
                    "kind": "mutation",
                    "mutation_id": parent_mutation_id,
                    "epoch_id": resolved_epoch_id,
                }
            edges.append({"from": parent_node_id, "to": mutation_node_id, "relation": "ancestor_of"})

    nodes = sorted(nodes_by_id.values(), key=lambda item: str(item.get("id") or ""))
    edges = sorted(edges, key=lambda item: (item["from"], item["to"], item["relation"]))
    return {
        "ok": True,
        "epoch_id": epoch_id,
        "window": len(events),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }


__all__ = ["build_evidence_graph_projection"]
