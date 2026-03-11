# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

import copy
import json
import time
from dataclasses import dataclass

from app.simulation_utils import LRUCache, clone_dna_for_simulation, stable_hash


@dataclass
class MutationHint:
    name: str
    weight: float


def test_deepcopy_preserves_tuples() -> None:
    dna = {
        "lineage": "agent-alpha",
        "traits": {
            "weights": (0.25, 0.5, 0.75),
            "anchors": (("focus", 1), ("risk", 2)),
        },
    }

    simulated = copy.deepcopy(dna)

    assert isinstance(simulated["traits"]["weights"], tuple)
    assert isinstance(simulated["traits"]["anchors"], tuple)
    assert simulated == dna


def test_deepcopy_preserves_nested_objects() -> None:
    dna = {
        "lineage": "agent-beta",
        "metadata": {
            "hint": MutationHint(name="conservative", weight=0.42),
        },
    }

    simulated = copy.deepcopy(dna)

    assert simulated == dna
    assert simulated is not dna
    assert simulated["metadata"] is not dna["metadata"]
    assert simulated["metadata"]["hint"] is not dna["metadata"]["hint"]


def test_deepcopy_vs_json_benchmark() -> None:
    shared_branch = {"weights": tuple(i / 100 for i in range(25)), "flags": {"safe": True, "tier": "standard"}}
    dna = {
        "lineage": "agent-gamma",
        "traits": {
            "branches": [shared_branch for _ in range(40)],
            "history": [{"epoch": i, "score": i / 100} for i in range(20)],
        },
    }
    iterations = 600

    start = time.perf_counter()
    for _ in range(iterations):
        copy.deepcopy(dna)
    deepcopy_time = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(iterations):
        json.loads(json.dumps(dna))
    json_time = time.perf_counter() - start

    assert deepcopy_time <= (json_time * 1.5)


def test_clone_preserves_shared_reference_structure() -> None:
    shared = {"node": 1}
    dna = {"lineage": "agent-delta", "a": shared, "b": shared}

    simulated = clone_dna_for_simulation(dna)

    assert simulated["a"] is simulated["b"]


def test_stable_hash_is_deterministic_for_equivalent_payloads() -> None:
    payload_a = {"parent": "x", "intent": "score", "content": {"k": [1, 2], "flag": True}}
    payload_b = {"intent": "score", "content": {"flag": True, "k": [1, 2]}, "parent": "x"}

    assert stable_hash(payload_a) == stable_hash(payload_b)


class _HashProbe:
    def __init__(self, x: int):
        self.x = x


def test_stable_hash_normalizes_custom_objects() -> None:
    payload_a = {"probe": _HashProbe(7), "meta": {"ok": True}}
    payload_b = {"meta": {"ok": True}, "probe": {"x": 7}}

    assert stable_hash(payload_a) == stable_hash(payload_b)


def test_stable_hash_distinguishes_tuple_from_list() -> None:
    tuple_payload = {"content": (1, 2, 3)}
    list_payload = {"content": [1, 2, 3]}

    assert stable_hash(tuple_payload) != stable_hash(list_payload)


def test_lru_cache_bounds_and_eviction_order() -> None:
    cache = LRUCache(maxsize=2)
    cache.set("a", 1.0)
    cache.set("b", 2.0)
    assert cache.get("a") == 1.0
    cache.set("c", 3.0)

    assert cache.get("b") is None
    assert cache.get("a") == 1.0
    assert cache.get("c") == 3.0


def test_stable_hash_tuple_marker_does_not_collide_with_user_dict() -> None:
    tuple_payload = {"content": ("x", "y")}
    user_dict_payload = {"content": {"__type__": "tuple", "items": ["x", "y"]}}

    assert stable_hash(tuple_payload) != stable_hash(user_dict_payload)


def test_clone_fallback_to_deepcopy_for_unsupported_type() -> None:
    hint = MutationHint(name="fallback", weight=0.9)
    dna = {"lineage": "agent-epsilon", "metadata": {"hint": hint}}

    try:
        clone_dna_for_simulation(dna)
    except TypeError as exc:
        assert str(exc) == "unsupported_dna_type:MutationHint"
    else:
        raise AssertionError("unsupported custom DNA payload should fail-closed")


def test_clone_supports_primitive_collection_payloads() -> None:
    dna = {
        "lineage": "agent-zeta",
        "flags": [True, False, None],
        "metrics": {"score": 0.91, "count": 4},
        "shape": ("stable", 3),
    }

    simulated = clone_dna_for_simulation(dna)

    assert simulated == dna
    assert simulated is not dna
    assert simulated["flags"] is not dna["flags"]
    assert simulated["metrics"] is not dna["metrics"]


def test_clone_rejection_keeps_original_dna_unchanged() -> None:
    hint = MutationHint(name="immutable", weight=0.4)
    dna = {"lineage": "agent-theta", "metadata": {"hint": hint}}
    original = copy.deepcopy(dna)

    try:
        clone_dna_for_simulation(dna)
    except TypeError as exc:
        assert str(exc) == "unsupported_dna_type:MutationHint"
    else:
        raise AssertionError("unsupported custom DNA payload should fail-closed")

    assert dna == original


def test_clone_permissive_fallback_requires_explicit_flag(monkeypatch) -> None:
    hint = MutationHint(name="legacy", weight=0.7)
    dna = {"lineage": "agent-iota", "metadata": {"hint": hint}}

    monkeypatch.setenv("ADAAD_SIMULATION_ALLOW_UNSUPPORTED_DNA_DEEPCOPY", "1")
    simulated = clone_dna_for_simulation(dna)

    assert simulated == dna
    assert simulated is not dna
    assert simulated["metadata"] is not dna["metadata"]
    assert simulated["metadata"]["hint"] is not hint


def test_stable_hash_supports_non_dict_payloads() -> None:
    assert stable_hash([1, 2, {"k": "v"}]) == stable_hash([1, 2, {"k": "v"}])


def test_stable_hash_supports_mixed_dict_key_types() -> None:
    payload_a = {"1": "string", 1: "int", b"1": "bytes", None: "none"}
    payload_b = {None: "none", b"1": "bytes", 1: "int", "1": "string"}

    assert stable_hash(payload_a) == stable_hash(payload_b)


def test_stable_hash_supports_nested_mixed_dict_key_types() -> None:
    payload_a = {
        "outer": {
            ("x", 1): {"1": "s", 1: "i"},
            3: {False: "b", None: "n"},
        }
    }
    payload_b = {
        "outer": {
            3: {None: "n", False: "b"},
            ("x", 1): {1: "i", "1": "s"},
        }
    }

    assert stable_hash(payload_a) == stable_hash(payload_b)


def test_stable_hash_digest_is_replay_stable_across_repeated_runs() -> None:
    payload = {
        "meta": {"run": 1, "flags": {"safe": True, "tier": 2}},
        "content": [{"id": i, "score": i / 10} for i in range(5)],
    }

    digest = stable_hash(payload)
    for _ in range(25):
        assert stable_hash(payload) == digest
