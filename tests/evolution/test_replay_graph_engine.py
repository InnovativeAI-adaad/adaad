# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
import random
from typing import Any, Dict, List

import pytest

from runtime.evolution.event_signing import DeterministicMockSigner
from runtime.evolution.replay_graph_engine import ReplayGraphValidationError, replay_traversal_events


def _canonical_json(value: Dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _event_hash(*, mutation_id: str, parent_mutation_id: str, ancestor_chain: List[str], payload: Dict[str, Any]) -> str:
    material = {
        "mutation_id": mutation_id,
        "parent_mutation_id": parent_mutation_id,
        "ancestor_chain": ancestor_chain,
        "event_type": "MutationBundleEvent",
        "payload": payload,
    }
    return hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()


def _entry(
    *,
    signer: DeterministicMockSigner,
    mutation_id: str,
    parent_mutation_id: str = "",
    ancestor_chain: List[str] | None = None,
) -> Dict[str, Any]:
    chain = ancestor_chain or ([] if not parent_mutation_id else [parent_mutation_id])
    payload: Dict[str, Any] = {
        "mutation_id": mutation_id,
        "parent_mutation_id": parent_mutation_id,
        "ancestor_chain": chain,
        "epoch_id": "epoch-aeo-1",
        "delta": {"op": "noop", "mutation_id": mutation_id},
    }
    event_hash = _event_hash(
        mutation_id=mutation_id,
        parent_mutation_id=parent_mutation_id,
        ancestor_chain=chain,
        payload=payload,
    )
    signature = signer.sign(event_hash)
    payload["signature"] = signature.signature
    payload["signing_key_id"] = signature.signing_key_id
    payload["signing_algorithm"] = signature.algorithm
    payload["prev_hash"] = ""
    return {
        "type": "MutationBundleEvent",
        "hash": event_hash,
        "payload": payload,
    }


def _wire_parent_hash(entries: List[Dict[str, Any]]) -> None:
    by_id = {str(entry["payload"]["mutation_id"]): entry for entry in entries}
    for entry in entries:
        parent = str(entry["payload"].get("parent_mutation_id") or "")
        if parent:
            entry["payload"]["prev_hash"] = str(by_id[parent]["hash"])


def test_replay_graph_engine_stable_order_under_input_permutation() -> None:
    signer = DeterministicMockSigner()
    entries = [
        _entry(signer=signer, mutation_id="m-root", parent_mutation_id="", ancestor_chain=[]),
        _entry(signer=signer, mutation_id="m-a", parent_mutation_id="m-root", ancestor_chain=["m-root"]),
        _entry(signer=signer, mutation_id="m-b", parent_mutation_id="m-root", ancestor_chain=["m-root"]),
        _entry(
            signer=signer,
            mutation_id="m-c",
            parent_mutation_id="m-a",
            ancestor_chain=["m-root", "m-a"],
        ),
    ]
    _wire_parent_hash(entries)

    expected = replay_traversal_events(
        aeo_ledger_entries=entries,
        aeo_index={"nodes": [], "edges": []},
        signature_verifier=signer.verify,
    )

    shuffled = list(entries)
    random.Random(20260319).shuffle(shuffled)
    observed = replay_traversal_events(
        aeo_ledger_entries=shuffled,
        aeo_index={"nodes": [], "edges": []},
        signature_verifier=signer.verify,
    )

    assert [item.mutation_id for item in observed] == [item.mutation_id for item in expected]


def test_replay_graph_engine_detects_lineage_discontinuity() -> None:
    signer = DeterministicMockSigner()
    orphan = _entry(
        signer=signer,
        mutation_id="m-orphan",
        parent_mutation_id="m-missing",
        ancestor_chain=["m-missing"],
    )

    with pytest.raises(ReplayGraphValidationError, match="lineage_discontinuity"):
        replay_traversal_events(
            aeo_ledger_entries=[orphan],
            aeo_index={"nodes": [], "edges": []},
            signature_verifier=signer.verify,
        )


def test_replay_graph_engine_rejects_signature_and_hash_mismatch() -> None:
    signer = DeterministicMockSigner()
    entry = _entry(signer=signer, mutation_id="m-hash")
    entry["hash"] = "0" * 64

    with pytest.raises(ReplayGraphValidationError, match="event_hash_mismatch"):
        replay_traversal_events(
            aeo_ledger_entries=[entry],
            aeo_index={"nodes": [], "edges": []},
            signature_verifier=signer.verify,
        )


def test_replay_graph_engine_reproducible_across_runs() -> None:
    signer = DeterministicMockSigner()
    entries = [
        _entry(signer=signer, mutation_id="m1", parent_mutation_id="", ancestor_chain=[]),
        _entry(signer=signer, mutation_id="m2", parent_mutation_id="m1", ancestor_chain=["m1"]),
    ]
    _wire_parent_hash(entries)
    index = {
        "nodes": [
            {
                "type": "MutationBundleEvent",
                "payload": {
                    "mutation_id": "m2",
                    "parent_mutation_id": "m1",
                    "ancestor_chain": ["m1"],
                    "epoch_id": "epoch-aeo-1",
                    "delta": {"op": "noop", "mutation_id": "m2"},
                    "signature": entries[1]["payload"]["signature"],
                    "signing_key_id": entries[1]["payload"]["signing_key_id"],
                    "signing_algorithm": entries[1]["payload"]["signing_algorithm"],
                    "prev_hash": entries[1]["payload"]["prev_hash"],
                },
                "hash": entries[1]["hash"],
            }
        ],
        "edges": [{"from_mutation_id": "m1", "to_mutation_id": "m2"}],
    }

    first = replay_traversal_events(aeo_ledger_entries=entries, aeo_index=index, signature_verifier=signer.verify)
    second = replay_traversal_events(aeo_ledger_entries=entries, aeo_index=index, signature_verifier=signer.verify)

    assert first == second
