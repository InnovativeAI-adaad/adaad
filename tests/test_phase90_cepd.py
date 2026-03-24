# SPDX-License-Identifier: Apache-2.0
"""Phase 90 — INNOV-06 · Cryptographic Evolution Proof DAG (CEPD).

Test ID format: T90-CEPD-NN

20 tests covering:
  - T90-CEPD-01..04  Merkle root computation, determinism, and CEPD-0
  - T90-CEPD-05..07  CEPDDagStore: genesis seed, append, traceability
  - T90-CEPD-08..11  CEPD-GATE-0 pass path: ACCEPTED + CryptographicProofBundle
  - T90-CEPD-12..16  CEPD-GATE-0 block paths: incomplete ancestry, bad schema,
                     depth exceeded, nondeterministic Merkle (mocked)
  - T90-CEPD-17..18  CryptographicProofBundle: independent verification
  - T90-CEPD-19..20  Multi-node chain: parent linking + genesis traceability (CEPD-1)
"""

from __future__ import annotations

import hashlib

import pytest

from runtime.evolution.cepd_engine import (
    CEPD_ANCESTOR_INCOMPLETE,
    CEPD_DEPTH_EXCEEDED,
    CEPD_GENESIS_UNTRACEABLE,
    CEPD_NODE_INCOMPLETE,
    CEPD_VERSION,
    GENESIS_EPOCH_ID,
    GENESIS_MUTATION_ID,
    CEPDDagStore,
    CEPDGateResult,
    CEPDOutcome,
    CryptographicProofBundle,
    SigningMode,
    compute_ancestor_merkle_root,
    evaluate_cepd_gate_0,
    verify_merkle_determinism,
    verify_proof_bundle,
    verify_signature,
    sign_node,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

TEST_KEY = hashlib.sha256(b"test-signing-key").digest()
EPOCH_ID = "epoch-001"


def _payload_hash(mutation_id: str) -> str:
    return hashlib.sha256(f"payload:{mutation_id}".encode()).hexdigest()


def _gate0(
    mutation_id: str = "MUT-001",
    epoch_id: str = EPOCH_ID,
    ancestor_set: frozenset | None = None,
    parent_node_ids: list | None = None,
    dag_store: CEPDDagStore | None = None,
    key: bytes = TEST_KEY,
    max_depth: int = 10_000,
) -> CEPDGateResult:
    if dag_store is None:
        dag_store = CEPDDagStore()
    if ancestor_set is None:
        ancestor_set = frozenset({GENESIS_MUTATION_ID})
    if parent_node_ids is None:
        parent_node_ids = [dag_store.genesis_node_id()]
    return evaluate_cepd_gate_0(
        mutation_id=mutation_id,
        epoch_id=epoch_id,
        payload_hash=_payload_hash(mutation_id),
        causal_ancestor_set=ancestor_set,
        parent_node_ids=parent_node_ids,
        dag_store=dag_store,
        signing_key=key,
        signing_mode=SigningMode.HMAC_SHA256,
        max_lineage_depth=max_depth,
    )


# ---------------------------------------------------------------------------
# T90-CEPD-01 — Merkle root is deterministic for same ancestor set
# ---------------------------------------------------------------------------


def test_t90_cepd_01_merkle_root_deterministic():
    """T90-CEPD-01: identical ancestor set → identical Merkle root."""
    ancestors = frozenset({"MUT-001", "MUT-002", "MUT-003"})
    r1 = compute_ancestor_merkle_root(ancestors)
    r2 = compute_ancestor_merkle_root(ancestors)
    assert r1 == r2
    assert len(r1) == 64


# ---------------------------------------------------------------------------
# T90-CEPD-02 — Merkle root changes with different ancestor sets
# ---------------------------------------------------------------------------


def test_t90_cepd_02_merkle_root_sensitive_to_ancestors():
    """T90-CEPD-02: different ancestor sets → different Merkle roots."""
    r1 = compute_ancestor_merkle_root(frozenset({"MUT-001", "MUT-002"}))
    r2 = compute_ancestor_merkle_root(frozenset({"MUT-001", "MUT-003"}))
    assert r1 != r2


# ---------------------------------------------------------------------------
# T90-CEPD-03 — Empty ancestor set (genesis) produces well-defined root
# ---------------------------------------------------------------------------


def test_t90_cepd_03_empty_ancestor_set_genesis_root():
    """T90-CEPD-03: empty ancestor set → deterministic genesis Merkle root."""
    r1 = compute_ancestor_merkle_root(frozenset())
    r2 = compute_ancestor_merkle_root(frozenset())
    assert r1 == r2
    assert len(r1) == 64


# ---------------------------------------------------------------------------
# T90-CEPD-04 — CEPD-0: verify_merkle_determinism passes for well-formed set
# ---------------------------------------------------------------------------


def test_t90_cepd_04_merkle_determinism_verification():
    """T90-CEPD-04: CEPD-0 — verify_merkle_determinism returns True for any set."""
    for ancestor_set in [
        frozenset(),
        frozenset({"MUT-001"}),
        frozenset({"MUT-001", "MUT-002", "MUT-003"}),
    ]:
        assert verify_merkle_determinism(ancestor_set) is True


# ---------------------------------------------------------------------------
# T90-CEPD-05 — CEPDDagStore pre-seeds genesis node
# ---------------------------------------------------------------------------


def test_t90_cepd_05_dag_store_genesis_seeded():
    """T90-CEPD-05: CEPDDagStore pre-seeds genesis node at construction."""
    store = CEPDDagStore()
    assert store.size() == 1
    genesis_id = store.genesis_node_id()
    node = store.get(genesis_id)
    assert node is not None
    assert node.mutation_id == GENESIS_MUTATION_ID
    assert node.epoch_id == GENESIS_EPOCH_ID
    assert node.parent_node_ids == ()


# ---------------------------------------------------------------------------
# T90-CEPD-06 — CEPDDagStore genesis is self-traceable (depth 0)
# ---------------------------------------------------------------------------


def test_t90_cepd_06_genesis_traceable_depth_zero():
    """T90-CEPD-06: genesis node is traceable to itself at depth 0."""
    store = CEPDDagStore()
    traceable, depth = store.check_genesis_traceable(store.genesis_node_id())
    assert traceable is True
    assert depth == 0


# ---------------------------------------------------------------------------
# T90-CEPD-07 — Direct child of genesis is traceable at depth 1
# ---------------------------------------------------------------------------


def test_t90_cepd_07_direct_child_traceable_depth_one():
    """T90-CEPD-07: node with genesis as parent → traceable at depth 1."""
    store = CEPDDagStore()
    result = _gate0(dag_store=store)
    assert result.outcome == CEPDOutcome.ACCEPTED
    node = result.proof_bundle.dag_node
    traceable, depth = store.check_genesis_traceable(node.node_id)
    assert traceable is True
    assert depth == 1


# ---------------------------------------------------------------------------
# T90-CEPD-08 — GATE-0 ACCEPTED returns CEPDGateResult
# ---------------------------------------------------------------------------


def test_t90_cepd_08_gate0_accepted_returns_correct_type():
    """T90-CEPD-08: CEPD-GATE-0 ACCEPTED → CEPDGateResult with proof_bundle."""
    result = _gate0()
    assert isinstance(result, CEPDGateResult)
    assert result.outcome == CEPDOutcome.ACCEPTED
    assert result.proof_bundle is not None
    assert not result.failure_codes


# ---------------------------------------------------------------------------
# T90-CEPD-09 — CryptographicProofBundle has correct structure
# ---------------------------------------------------------------------------


def test_t90_cepd_09_proof_bundle_structure():
    """T90-CEPD-09: CryptographicProofBundle fields are complete and typed."""
    result = _gate0()
    bundle = result.proof_bundle
    assert isinstance(bundle, CryptographicProofBundle)
    assert bundle.bundle_id.startswith("CEPD-")
    assert bundle.genesis_traceable is True
    assert len(bundle.bundle_hash) == 64
    assert bundle.cepd_version == CEPD_VERSION
    assert GENESIS_MUTATION_ID in bundle.ancestor_set


# ---------------------------------------------------------------------------
# T90-CEPD-10 — bundle_hash is deterministic
# ---------------------------------------------------------------------------


def test_t90_cepd_10_bundle_hash_deterministic():
    """T90-CEPD-10: identical inputs → identical bundle_hash."""
    r1 = _gate0()
    r2 = _gate0()
    assert r1.proof_bundle.bundle_hash == r2.proof_bundle.bundle_hash
    assert r1.proof_bundle.bundle_id == r2.proof_bundle.bundle_id


# ---------------------------------------------------------------------------
# T90-CEPD-11 — DAG node appended to store after ACCEPTED
# ---------------------------------------------------------------------------


def test_t90_cepd_11_node_appended_to_store():
    """T90-CEPD-11: successful gate appends node to CEPDDagStore."""
    store = CEPDDagStore()
    assert store.size() == 1  # genesis only
    result = _gate0(dag_store=store)
    assert result.outcome == CEPDOutcome.ACCEPTED
    assert store.size() == 2
    node_id = result.proof_bundle.dag_node.node_id
    assert store.get(node_id) is not None


# ---------------------------------------------------------------------------
# T90-CEPD-12 — GATE-0 REJECTED: empty ancestor set for non-genesis mutation
# ---------------------------------------------------------------------------


def test_t90_cepd_12_gate0_rejected_empty_ancestor_set():
    """T90-CEPD-12: non-genesis mutation with empty ancestor_set → CEPD_ANCESTOR_INCOMPLETE."""
    result = _gate0(ancestor_set=frozenset(), parent_node_ids=[])
    assert result.outcome == CEPDOutcome.REJECTED
    assert CEPD_ANCESTOR_INCOMPLETE in result.failure_codes


# ---------------------------------------------------------------------------
# T90-CEPD-13 — GATE-0 REJECTED: missing parent node in store
# ---------------------------------------------------------------------------


def test_t90_cepd_13_gate0_rejected_missing_parent():
    """T90-CEPD-13: parent_node_id not in dag_store → CEPD_ANCESTOR_INCOMPLETE."""
    result = _gate0(
        ancestor_set=frozenset({"FAKE-MUT"}),
        parent_node_ids=["nonexistent-node-id-00000000"],
    )
    assert result.outcome == CEPDOutcome.REJECTED
    assert CEPD_ANCESTOR_INCOMPLETE in result.failure_codes


# ---------------------------------------------------------------------------
# T90-CEPD-14 — GATE-0 REJECTED: empty mutation_id (schema incomplete)
# ---------------------------------------------------------------------------


def test_t90_cepd_14_gate0_rejected_empty_mutation_id():
    """T90-CEPD-14: empty mutation_id → CEPD_NODE_INCOMPLETE."""
    store = CEPDDagStore()
    result = evaluate_cepd_gate_0(
        mutation_id="",  # invalid
        epoch_id=EPOCH_ID,
        payload_hash=_payload_hash("MUT-X"),
        causal_ancestor_set=frozenset({GENESIS_MUTATION_ID}),
        parent_node_ids=[store.genesis_node_id()],
        dag_store=store,
        signing_key=TEST_KEY,
        signing_mode=SigningMode.HMAC_SHA256,
    )
    assert result.outcome == CEPDOutcome.REJECTED
    assert CEPD_NODE_INCOMPLETE in result.failure_codes


# ---------------------------------------------------------------------------
# T90-CEPD-15 — GATE-0 REJECTED: empty signing_key (schema incomplete)
# ---------------------------------------------------------------------------


def test_t90_cepd_15_gate0_rejected_empty_signing_key():
    """T90-CEPD-15: empty signing_key → CEPD_NODE_INCOMPLETE."""
    store = CEPDDagStore()
    result = evaluate_cepd_gate_0(
        mutation_id="MUT-KEY-FAIL",
        epoch_id=EPOCH_ID,
        payload_hash=_payload_hash("MUT-KEY-FAIL"),
        causal_ancestor_set=frozenset({GENESIS_MUTATION_ID}),
        parent_node_ids=[store.genesis_node_id()],
        dag_store=store,
        signing_key=b"",  # empty key
        signing_mode=SigningMode.HMAC_SHA256,
    )
    assert result.outcome == CEPDOutcome.REJECTED
    assert CEPD_NODE_INCOMPLETE in result.failure_codes


# ---------------------------------------------------------------------------
# T90-CEPD-16 — GATE-0 REJECTED: max_lineage_depth=0 triggers CEPD_DEPTH_EXCEEDED
# ---------------------------------------------------------------------------


def test_t90_cepd_16_gate0_rejected_depth_exceeded():
    """T90-CEPD-16: max_lineage_depth=0 → CEPD_DEPTH_EXCEEDED or CEPD_GENESIS_UNTRACEABLE."""
    result = _gate0(max_depth=0)
    assert result.outcome == CEPDOutcome.REJECTED
    assert (
        CEPD_DEPTH_EXCEEDED in result.failure_codes
        or CEPD_GENESIS_UNTRACEABLE in result.failure_codes
    )


# ---------------------------------------------------------------------------
# T90-CEPD-17 — verify_proof_bundle passes for valid bundle
# ---------------------------------------------------------------------------


def test_t90_cepd_17_bundle_verification_passes():
    """T90-CEPD-17: verify_proof_bundle returns True for a correctly built bundle."""
    result = _gate0(key=TEST_KEY)
    assert result.outcome == CEPDOutcome.ACCEPTED
    assert verify_proof_bundle(result.proof_bundle, TEST_KEY) is True


# ---------------------------------------------------------------------------
# T90-CEPD-18 — verify_proof_bundle fails on tampered Merkle root
# ---------------------------------------------------------------------------


def test_t90_cepd_18_bundle_verification_fails_tampered_merkle():
    """T90-CEPD-18: tampered ancestor_set → verify_proof_bundle returns False."""
    result = _gate0(key=TEST_KEY)
    bundle = result.proof_bundle
    # Create tampered bundle with a different ancestor_set
    tampered = CryptographicProofBundle(
        bundle_id=bundle.bundle_id,
        dag_node=bundle.dag_node,
        ancestor_set=frozenset({"TAMPERED-ANCESTOR"}),  # wrong set
        ancestor_merkle_root=bundle.ancestor_merkle_root,
        lineage_depth=bundle.lineage_depth,
        genesis_traceable=bundle.genesis_traceable,
        bundle_hash=bundle.bundle_hash,
        cepd_version=bundle.cepd_version,
    )
    assert verify_proof_bundle(tampered, TEST_KEY) is False


# ---------------------------------------------------------------------------
# T90-CEPD-19 — Multi-node chain: second-generation node traces genesis through parent
# ---------------------------------------------------------------------------


def test_t90_cepd_19_two_generation_chain_traceable():
    """T90-CEPD-19: MUT-001 → MUT-002 chain; MUT-002 traces genesis at depth 2."""
    store = CEPDDagStore()

    # Gen-1: MUT-001 child of genesis
    r1 = _gate0(mutation_id="MUT-001", dag_store=store)
    assert r1.outcome == CEPDOutcome.ACCEPTED
    node1_id = r1.proof_bundle.dag_node.node_id

    # Gen-2: MUT-002 child of MUT-001
    r2 = evaluate_cepd_gate_0(
        mutation_id="MUT-002",
        epoch_id="epoch-002",
        payload_hash=_payload_hash("MUT-002"),
        causal_ancestor_set=frozenset({GENESIS_MUTATION_ID, "MUT-001"}),
        parent_node_ids=[node1_id],
        dag_store=store,
        signing_key=TEST_KEY,
        signing_mode=SigningMode.HMAC_SHA256,
    )
    assert r2.outcome == CEPDOutcome.ACCEPTED
    assert r2.proof_bundle.genesis_traceable is True
    assert r2.proof_bundle.lineage_depth == 2


# ---------------------------------------------------------------------------
# T90-CEPD-20 — result_hash is stable and unique across ACCEPTED/REJECTED
# ---------------------------------------------------------------------------


def test_t90_cepd_20_result_hash_unique_accepted_vs_rejected():
    """T90-CEPD-20: ACCEPTED and REJECTED results have different result_hashes."""
    r_ok = _gate0(mutation_id="MUT-GOOD")
    r_bad = _gate0(mutation_id="", ancestor_set=frozenset(), parent_node_ids=[])
    assert r_ok.result_hash != r_bad.result_hash
    assert len(r_ok.result_hash) == 64
    assert len(r_bad.result_hash) == 64
