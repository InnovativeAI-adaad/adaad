# SPDX-License-Identifier: Apache-2.0
"""Deterministic replay graph traversal over normalized AEO ledger/index outputs."""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence

from runtime.evolution.event_signing import SignatureBundle


class ReplayGraphValidationError(RuntimeError):
    """Raised when replay graph validation fails."""


@dataclass(frozen=True)
class ReplayGraphNode:
    """Canonical normalized replay node."""

    node_id: str
    mutation_id: str
    parent_mutation_id: str
    ancestor_chain: tuple[str, ...]
    event_type: str
    payload: Mapping[str, Any]
    event_hash: str
    parent_hash: str
    signature: str
    signing_key_id: str
    signing_algorithm: str


@dataclass(frozen=True)
class ReplayTraversalEvent:
    """Deterministic in-memory replay event consumed by state machines."""

    sequence: int
    node_id: str
    mutation_id: str
    parent_mutation_id: str
    event_type: str
    event_hash: str


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _extract_lineage_payload(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = raw.get("payload") if isinstance(raw.get("payload"), Mapping) else raw
    return payload if isinstance(payload, Mapping) else {}


def _normalize_ancestor_chain(payload: Mapping[str, Any], certificate: Mapping[str, Any]) -> tuple[str, ...]:
    raw_chain = (
        payload.get("ancestor_chain")
        or payload.get("ancestor_mutation_ids")
        or certificate.get("ancestor_chain")
        or certificate.get("ancestor_mutation_ids")
        or []
    )
    if not isinstance(raw_chain, Sequence) or isinstance(raw_chain, (str, bytes)):
        return ()
    return tuple(str(item).strip() for item in raw_chain if str(item).strip())


def _normalize_node(raw: Mapping[str, Any]) -> ReplayGraphNode | None:
    payload = _extract_lineage_payload(raw)
    if not payload:
        return None

    certificate = payload.get("certificate") if isinstance(payload.get("certificate"), Mapping) else {}
    mutation_id = str(
        payload.get("mutation_id")
        or payload.get("bundle_id")
        or certificate.get("mutation_id")
        or certificate.get("bundle_id")
        or ""
    ).strip()
    if not mutation_id:
        return None

    parent_mutation_id = str(
        payload.get("parent_mutation_id")
        or payload.get("parent_bundle_id")
        or certificate.get("parent_mutation_id")
        or certificate.get("parent_bundle_id")
        or ""
    ).strip()

    event_type = str(raw.get("type") or payload.get("type") or "MutationBundleEvent").strip()

    event_hash = str(
        raw.get("hash")
        or payload.get("event_hash")
        or payload.get("hash")
        or certificate.get("event_hash")
        or certificate.get("hash")
        or ""
    ).strip()
    parent_hash = str(
        payload.get("prev_hash")
        or payload.get("parent_hash")
        or certificate.get("prev_hash")
        or certificate.get("parent_hash")
        or ""
    ).strip()

    signature = str(
        payload.get("signature")
        or certificate.get("signature")
        or ""
    ).strip()
    signing_key_id = str(
        payload.get("signing_key_id")
        or certificate.get("signing_key_id")
        or ""
    ).strip()
    signing_algorithm = str(
        payload.get("signing_algorithm")
        or certificate.get("signing_algorithm")
        or ""
    ).strip()

    node_id = str(raw.get("node_id") or payload.get("node_id") or f"mutation:{mutation_id}").strip()

    canonical_payload: Dict[str, Any] = {
        k: v
        for k, v in dict(payload).items()
        if k
        not in {
            "signature",
            "hash",
            "event_hash",
            "signing_key_id",
            "signing_algorithm",
            "prev_hash",
            "parent_hash",
        }
    }

    return ReplayGraphNode(
        node_id=node_id,
        mutation_id=mutation_id,
        parent_mutation_id=parent_mutation_id,
        ancestor_chain=_normalize_ancestor_chain(payload, certificate),
        event_type=event_type,
        payload=canonical_payload,
        event_hash=event_hash,
        parent_hash=parent_hash,
        signature=signature,
        signing_key_id=signing_key_id,
        signing_algorithm=signing_algorithm,
    )


def load_normalized_evidence_graph(
    *,
    aeo_ledger_entries: Iterable[Mapping[str, Any]],
    aeo_index: Mapping[str, Any],
) -> tuple[List[ReplayGraphNode], List[tuple[str, str]]]:
    """Load canonical nodes/edges from AEO ledger + index payloads."""

    nodes_by_mutation: Dict[str, ReplayGraphNode] = {}

    for raw in aeo_ledger_entries:
        if not isinstance(raw, Mapping):
            continue
        node = _normalize_node(raw)
        if node is not None:
            nodes_by_mutation[node.mutation_id] = node

    index_nodes = aeo_index.get("nodes") if isinstance(aeo_index, Mapping) else None
    if isinstance(index_nodes, Sequence):
        for raw in index_nodes:
            if not isinstance(raw, Mapping):
                continue
            node = _normalize_node(raw)
            if node is None:
                continue
            existing = nodes_by_mutation.get(node.mutation_id)
            if existing is None or len(_canonical_json(node.payload)) > len(_canonical_json(existing.payload)):
                nodes_by_mutation[node.mutation_id] = node

    nodes = sorted(nodes_by_mutation.values(), key=lambda item: (item.mutation_id, item.node_id))

    edges: set[tuple[str, str]] = set()
    for node in nodes:
        if node.parent_mutation_id:
            edges.add((node.parent_mutation_id, node.mutation_id))

    index_edges = aeo_index.get("edges") if isinstance(aeo_index, Mapping) else None
    if isinstance(index_edges, Sequence):
        for edge in index_edges:
            if not isinstance(edge, Mapping):
                continue
            parent = str(edge.get("from_mutation_id") or edge.get("from") or "").strip()
            child = str(edge.get("to_mutation_id") or edge.get("to") or "").strip()
            if parent.startswith("mutation:"):
                parent = parent.split(":", 1)[1]
            if child.startswith("mutation:"):
                child = child.split(":", 1)[1]
            if parent and child:
                edges.add((parent, child))

    return nodes, sorted(edges)


def _canonical_event_hash(node: ReplayGraphNode) -> str:
    material = {
        "mutation_id": node.mutation_id,
        "parent_mutation_id": node.parent_mutation_id,
        "ancestor_chain": list(node.ancestor_chain),
        "event_type": node.event_type,
        "payload": node.payload,
    }
    return hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()


def _validate_lineage(nodes: Sequence[ReplayGraphNode]) -> None:
    by_id = {node.mutation_id: node for node in nodes}
    for node in nodes:
        if node.parent_mutation_id and node.parent_mutation_id not in by_id:
            raise ReplayGraphValidationError(f"lineage_discontinuity:missing_parent:{node.mutation_id}:{node.parent_mutation_id}")

        chain = node.ancestor_chain
        if not chain:
            continue
        if node.parent_mutation_id and chain[-1] != node.parent_mutation_id:
            raise ReplayGraphValidationError(f"lineage_discontinuity:parent_chain_tail:{node.mutation_id}")

        for ancestor in chain:
            if ancestor not in by_id:
                raise ReplayGraphValidationError(f"lineage_discontinuity:missing_ancestor:{node.mutation_id}:{ancestor}")

        if len(set(chain)) != len(chain):
            raise ReplayGraphValidationError(f"lineage_cycle_detected:ancestor_chain:{node.mutation_id}")

        if node.mutation_id in set(chain):
            raise ReplayGraphValidationError(f"lineage_cycle_detected:self_reference:{node.mutation_id}")


def _validate_hash_and_signature(
    nodes: Sequence[ReplayGraphNode],
    *,
    signature_verifier: Callable[..., bool] | None,
) -> None:
    by_id = {node.mutation_id: node for node in nodes}
    for node in nodes:
        expected_hash = _canonical_event_hash(node)
        if node.event_hash != expected_hash:
            raise ReplayGraphValidationError(f"event_hash_mismatch:{node.mutation_id}")

        if node.parent_mutation_id and node.parent_hash:
            parent = by_id.get(node.parent_mutation_id)
            if parent is None:
                raise ReplayGraphValidationError(f"lineage_discontinuity:missing_parent:{node.mutation_id}:{node.parent_mutation_id}")
            if node.parent_hash != parent.event_hash:
                raise ReplayGraphValidationError(f"parent_hash_mismatch:{node.mutation_id}")

        if signature_verifier is not None:
            if not (node.signature and node.signing_key_id and node.signing_algorithm):
                raise ReplayGraphValidationError(f"signature_missing:{node.mutation_id}")
            valid = signature_verifier(
                message=expected_hash,
                signature=SignatureBundle(
                    signature=node.signature,
                    signing_key_id=node.signing_key_id,
                    algorithm=node.signing_algorithm,
                ),
            )
            if not valid:
                raise ReplayGraphValidationError(f"signature_invalid:{node.mutation_id}")


def canonical_topological_order(nodes: Sequence[ReplayGraphNode], edges: Sequence[tuple[str, str]]) -> List[ReplayGraphNode]:
    """Return stable topological order with deterministic lexical tie-breakers."""

    by_id = {node.mutation_id: node for node in nodes}
    indegree: Dict[str, int] = {node.mutation_id: 0 for node in nodes}
    adjacency: Dict[str, List[str]] = defaultdict(list)

    for parent, child in edges:
        if parent not in by_id or child not in by_id:
            raise ReplayGraphValidationError(f"lineage_discontinuity:edge_unknown_node:{parent}->{child}")
        adjacency[parent].append(child)
        indegree[child] += 1

    for children in adjacency.values():
        children.sort()

    queue = sorted([node_id for node_id, degree in indegree.items() if degree == 0])
    ordered_ids: List[str] = []

    while queue:
        current = queue.pop(0)
        ordered_ids.append(current)
        for child in adjacency.get(current, []):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
        queue.sort()

    if len(ordered_ids) != len(nodes):
        raise ReplayGraphValidationError("lineage_cycle_detected:topological_sort")

    return [by_id[node_id] for node_id in ordered_ids]


def replay_traversal_events(
    *,
    aeo_ledger_entries: Iterable[Mapping[str, Any]],
    aeo_index: Mapping[str, Any],
    signature_verifier: Callable[..., bool] | None = None,
) -> List[ReplayTraversalEvent]:
    """Generate deterministic in-memory traversal events (pure, side-effect free)."""

    nodes, edges = load_normalized_evidence_graph(aeo_ledger_entries=aeo_ledger_entries, aeo_index=aeo_index)
    _validate_lineage(nodes)
    _validate_hash_and_signature(nodes, signature_verifier=signature_verifier)
    ordered = canonical_topological_order(nodes, edges)

    return [
        ReplayTraversalEvent(
            sequence=index,
            node_id=node.node_id,
            mutation_id=node.mutation_id,
            parent_mutation_id=node.parent_mutation_id,
            event_type=node.event_type,
            event_hash=node.event_hash,
        )
        for index, node in enumerate(ordered)
    ]


__all__ = [
    "ReplayGraphNode",
    "ReplayGraphValidationError",
    "ReplayTraversalEvent",
    "canonical_topological_order",
    "load_normalized_evidence_graph",
    "replay_traversal_events",
]
