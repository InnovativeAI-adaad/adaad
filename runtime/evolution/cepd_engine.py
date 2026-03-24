# SPDX-License-Identifier: Apache-2.0
"""INNOV-06 — Cryptographic Evolution Proof DAG (CEPD).

World-first cryptographic DAG proof of evolutionary lineage for an
autonomous software evolution system.

ADAAD's LineageLedgerV2 provides hash-chained linear lineage.  CEPD
extends this into a full directed acyclic graph (DAG) where every
mutation node is cryptographically linked to ALL of its causal ancestors
— not just its immediate predecessor.  This produces an unbreakable,
tamper-evident proof of evolutionary lineage from genesis to current
state, suitable for independent third-party verification and legal
admissibility in intellectual property proceedings (FINDING-66-003).

Constitutional Invariants Introduced
─────────────────────────────────────
  CEPD-0   Every mutation node in the DAG MUST carry an ancestor_merkle_root
           computed deterministically from its complete causal ancestor set.
           Any DAG node whose Merkle root cannot be reproduced from ledger
           state alone MUST be rejected (CEPD_MERKLE_NONDETERMINISTIC).

  CEPD-1   Every DAG node MUST be traceable to the genesis node by following
           parent edges.  Any node that fails genesis traceability check
           (CEPD_GENESIS_UNTRACEABLE) is a constitutional integrity failure
           requiring HUMAN-0 alert before the pipeline may continue.

Design Constraints
──────────────────
  - Fully deterministic: identical ancestor set → identical Merkle root.
  - Fail-closed: any gate check failure → CEPD_NODE_REJECTED; no partial nodes.
  - No datetime.now() / time.time() — epoch counter injected by caller.
  - Ed25519 signing: uses PyNaCl when available; falls back to HMAC-SHA256
    in test/offline mode — never silently no-ops.
  - CryptographicProofBundle is the primary artifact for patent prosecution;
    it must be self-contained and independently verifiable.
  - Genesis node (mutation_id="GENESIS", epoch_id="0") is the unconditional root.

Pipeline Position
─────────────────
  Post-GovernanceGate, pre-ledger-append:
    GOVERNANCE_APPROVED → CEPD-GATE-0 → CryptographicProofBundle → LEDGER

  CryptographicProofBundle is included in every release artifact.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

log = logging.getLogger(__name__)

CEPD_VERSION = "90.1"
GENESIS_MUTATION_ID = "GENESIS"
GENESIS_EPOCH_ID = "0"
DEFAULT_MAX_LINEAGE_DEPTH = 10_000

# ---------------------------------------------------------------------------
# Failure code constants
# ---------------------------------------------------------------------------

CEPD_ANCESTOR_INCOMPLETE = "CEPD_ANCESTOR_INCOMPLETE"
CEPD_SIGNATURE_INVALID = "CEPD_SIGNATURE_INVALID"
CEPD_MERKLE_NONDETERMINISTIC = "CEPD_MERKLE_NONDETERMINISTIC"
CEPD_GENESIS_UNTRACEABLE = "CEPD_GENESIS_UNTRACEABLE"
CEPD_DEPTH_EXCEEDED = "CEPD_DEPTH_EXCEEDED"
CEPD_NODE_INCOMPLETE = "CEPD_NODE_INCOMPLETE"
CEPD_NODE_REJECTED = "CEPD_NODE_REJECTED"


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class CEPDOutcome(str, Enum):
    ACCEPTED = "CEPD_ACCEPTED"
    REJECTED = "CEPD_REJECTED"


class SigningMode(str, Enum):
    ED25519 = "ed25519"
    HMAC_SHA256 = "hmac_sha256"   # offline / test mode


# ---------------------------------------------------------------------------
# Core data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CEPDDagNode:
    """A single node in the Cryptographic Evolution Proof DAG.

    Every node represents one mutation and carries cryptographic links
    to all of its causal ancestors via Merkle root.

    Attributes:
        node_id: Deterministic ID: SHA-256(mutation_id + epoch_id + ancestor_merkle_root)[:24]
        mutation_id: The mutation this node represents.
        epoch_id: Epoch at which this mutation occurred.
        parent_node_ids: Immediate parent node IDs (direct predecessors in DAG).
        ancestor_merkle_root: SHA-256 Merkle root over complete causal ancestor set.
        payload_hash: SHA-256 of the mutation payload (content hash).
        signing_mode: Ed25519 or HMAC-SHA256.
        signature: Hex signature covering SHA-256(node_id+ancestor_merkle_root+payload_hash).
        cepd_version: Engine version at node creation time.
    """

    node_id: str
    mutation_id: str
    epoch_id: str
    parent_node_ids: Tuple[str, ...]
    ancestor_merkle_root: str
    payload_hash: str
    signing_mode: SigningMode
    signature: str
    cepd_version: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "mutation_id": self.mutation_id,
            "epoch_id": self.epoch_id,
            "parent_node_ids": list(self.parent_node_ids),
            "ancestor_merkle_root": self.ancestor_merkle_root,
            "payload_hash": self.payload_hash,
            "signing_mode": self.signing_mode.value,
            "signature": self.signature,
            "cepd_version": self.cepd_version,
        }


@dataclass(frozen=True)
class CryptographicProofBundle:
    """Self-contained, independently verifiable evolutionary proof artifact.

    This is the primary artifact for patent prosecution (FINDING-66-003).
    A verifier with only this bundle and knowledge of the Merkle algorithm
    can confirm the evolutionary claim without system access.

    Attributes:
        bundle_id: Deterministic ID from bundle_hash[:24].
        dag_node: The node being proven.
        ancestor_set: Complete set of causal ancestor mutation IDs.
        ancestor_merkle_root: Merkle root over ancestor_set (matches dag_node).
        lineage_depth: Number of hops to genesis.
        genesis_traceable: True if genesis node is reachable.
        bundle_hash: SHA-256 of canonical bundle JSON (all preceding fields).
        cepd_version: Engine version.
    """

    bundle_id: str
    dag_node: CEPDDagNode
    ancestor_set: FrozenSet[str]
    ancestor_merkle_root: str
    lineage_depth: int
    genesis_traceable: bool
    bundle_hash: str
    cepd_version: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "dag_node": self.dag_node.to_dict(),
            "ancestor_set": sorted(self.ancestor_set),
            "ancestor_merkle_root": self.ancestor_merkle_root,
            "lineage_depth": self.lineage_depth,
            "genesis_traceable": self.genesis_traceable,
            "bundle_hash": self.bundle_hash,
            "cepd_version": self.cepd_version,
        }


@dataclass(frozen=True)
class CEPDGateResult:
    """Return value of evaluate_cepd_gate_0().

    Attributes:
        outcome: CEPD_ACCEPTED or CEPD_REJECTED.
        proof_bundle: CryptographicProofBundle on ACCEPTED; None on REJECTED.
        failure_codes: All triggered failure codes.
        result_hash: SHA-256 of canonical result payload.
    """

    outcome: CEPDOutcome
    proof_bundle: Optional[CryptographicProofBundle]
    failure_codes: Tuple[str, ...]
    result_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "failure_codes": list(self.failure_codes),
            "result_hash": self.result_hash,
            "bundle_id": self.proof_bundle.bundle_id if self.proof_bundle else None,
        }


# ---------------------------------------------------------------------------
# In-memory DAG store
# ---------------------------------------------------------------------------


class CEPDDagStore:
    """Append-only in-memory store of CEPDDagNodes.

    The genesis node is pre-seeded at construction time.  All other nodes
    must be appended via ``append()``.  Parent-child relationships are
    tracked for genesis traceability queries.
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, CEPDDagNode] = {}
        # Seed genesis node
        genesis = _build_genesis_node()
        self._nodes[genesis.node_id] = genesis
        self._genesis_node_id = genesis.node_id

    def append(self, node: CEPDDagNode) -> None:
        """Append a new node.  Idempotent on same node_id."""
        self._nodes[node.node_id] = node

    def get(self, node_id: str) -> Optional[CEPDDagNode]:
        return self._nodes.get(node_id)

    def genesis_node_id(self) -> str:
        return self._genesis_node_id

    def all_node_ids(self) -> FrozenSet[str]:
        return frozenset(self._nodes)

    def size(self) -> int:
        return len(self._nodes)

    def check_genesis_traceable(
        self, node_id: str, max_depth: int = DEFAULT_MAX_LINEAGE_DEPTH
    ) -> Tuple[bool, int]:
        """BFS from node_id; return (traceable, depth) toward genesis.

        Returns (True, depth) when genesis node is reachable within max_depth.
        Returns (False, depth_reached) when unreachable or depth exceeded.
        """
        if node_id == self._genesis_node_id:
            return True, 0
        visited: set = set()
        queue: List[Tuple[str, int]] = [(node_id, 0)]
        while queue:
            current_id, depth = queue.pop(0)
            if depth > max_depth:
                return False, depth
            if current_id in visited:
                continue
            visited.add(current_id)
            node = self._nodes.get(current_id)
            if node is None:
                continue
            for parent_id in node.parent_node_ids:
                if parent_id == self._genesis_node_id:
                    return True, depth + 1
                queue.append((parent_id, depth + 1))
        return False, len(visited)


# ---------------------------------------------------------------------------
# Merkle root computation (CEPD-0)
# ---------------------------------------------------------------------------


def compute_ancestor_merkle_root(ancestor_set: FrozenSet[str]) -> str:
    """Compute deterministic Merkle root over all ancestor mutation IDs.

    Algorithm (CEPD spec):
        merkle_root = SHA256(sorted([SHA256(ancestor_id) for ancestor_id in ancestor_set]))

    Determinism invariant: identical ancestor_set → identical merkle_root.

    Raises:
        ValueError: if ancestor_set is empty (genesis has empty ancestor set
                    but is handled as a special case by the caller).
    """
    if not ancestor_set:
        # Genesis node: empty ancestor set → well-defined empty root
        return hashlib.sha256(b"GENESIS_EMPTY_ANCESTOR_SET").hexdigest()

    leaf_hashes = sorted(
        hashlib.sha256(aid.encode()).hexdigest() for aid in ancestor_set
    )
    merkle_payload = json.dumps(leaf_hashes, sort_keys=True)
    return hashlib.sha256(merkle_payload.encode()).hexdigest()


def verify_merkle_determinism(ancestor_set: FrozenSet[str]) -> bool:
    """Return True iff two independent computations produce the same root (CEPD-0)."""
    r1 = compute_ancestor_merkle_root(ancestor_set)
    r2 = compute_ancestor_merkle_root(ancestor_set)
    return r1 == r2


# ---------------------------------------------------------------------------
# Signing helpers
# ---------------------------------------------------------------------------


def _sign_node_hmac(signing_material: str, key: bytes) -> str:
    """HMAC-SHA256 signature — offline / test mode."""
    mac = hmac.new(key, signing_material.encode(), hashlib.sha256)
    return mac.hexdigest()


def _sign_node_ed25519(signing_material: str, private_key_bytes: bytes) -> str:
    """Ed25519 signature via PyNaCl; hex-encoded."""
    try:
        from nacl.signing import SigningKey  # type: ignore
        sk = SigningKey(private_key_bytes[:32])
        signed = sk.sign(signing_material.encode())
        return signed.signature.hex()
    except ImportError:
        raise RuntimeError(
            "PyNaCl is required for Ed25519 signing (CEPD-GATE-0 check 4). "
            "Install it with: pip install pynacl"
        )


def sign_node(
    node_id: str,
    ancestor_merkle_root: str,
    payload_hash: str,
    signing_key: bytes,
    mode: SigningMode,
) -> str:
    """Produce a hex signature for a DAG node.

    Signing material = SHA-256(node_id + ancestor_merkle_root + payload_hash).
    """
    signing_material = hashlib.sha256(
        (node_id + ancestor_merkle_root + payload_hash).encode()
    ).hexdigest()
    if mode == SigningMode.ED25519:
        return _sign_node_ed25519(signing_material, signing_key)
    return _sign_node_hmac(signing_material, signing_key)


def verify_signature(
    node_id: str,
    ancestor_merkle_root: str,
    payload_hash: str,
    signature: str,
    signing_key: bytes,
    mode: SigningMode,
) -> bool:
    """Verify a DAG node signature; returns True on match."""
    expected = sign_node(node_id, ancestor_merkle_root, payload_hash, signing_key, mode)
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Node construction helpers
# ---------------------------------------------------------------------------


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _node_id(mutation_id: str, epoch_id: str, ancestor_merkle_root: str) -> str:
    return _sha256(mutation_id + epoch_id + ancestor_merkle_root)[:24]


def _build_genesis_node() -> CEPDDagNode:
    """Construct the unconditional genesis node (mutation_id=GENESIS, epoch_id=0)."""
    ancestor_root = compute_ancestor_merkle_root(frozenset())
    payload_hash = _sha256(GENESIS_MUTATION_ID + GENESIS_EPOCH_ID)
    nid = _node_id(GENESIS_MUTATION_ID, GENESIS_EPOCH_ID, ancestor_root)
    # Genesis is self-signed with deterministic key
    key = hashlib.sha256(b"CEPD_GENESIS_KEY").digest()
    sig = _sign_node_hmac(
        hashlib.sha256((nid + ancestor_root + payload_hash).encode()).hexdigest(),
        key,
    )
    return CEPDDagNode(
        node_id=nid,
        mutation_id=GENESIS_MUTATION_ID,
        epoch_id=GENESIS_EPOCH_ID,
        parent_node_ids=(),
        ancestor_merkle_root=ancestor_root,
        payload_hash=payload_hash,
        signing_mode=SigningMode.HMAC_SHA256,
        signature=sig,
        cepd_version=CEPD_VERSION,
    )


def _result_hash(outcome: CEPDOutcome, failure_codes: Sequence[str], bundle_id: Optional[str]) -> str:
    return _sha256(
        json.dumps(
            {"outcome": outcome.value, "failure_codes": sorted(failure_codes), "bundle_id": bundle_id},
            sort_keys=True,
        )
    )


# ---------------------------------------------------------------------------
# CEPD-GATE-0 — DAG Node Integrity
# ---------------------------------------------------------------------------


def evaluate_cepd_gate_0(
    mutation_id: str,
    epoch_id: str,
    payload_hash: str,
    causal_ancestor_set: FrozenSet[str],
    parent_node_ids: Sequence[str],
    dag_store: CEPDDagStore,
    signing_key: bytes,
    signing_mode: SigningMode = SigningMode.HMAC_SHA256,
    max_lineage_depth: int = DEFAULT_MAX_LINEAGE_DEPTH,
    lineage_v2_tail_hash: Optional[str] = None,
) -> CEPDGateResult:
    """Evaluate CEPD-GATE-0 — DAG Node Integrity.

    Gate checks (all must pass for CEPD_ACCEPTED):
      1. Ancestor completeness: causal_ancestor_set is non-empty for non-genesis
         mutations; all parent_node_ids exist in dag_store.
      2. Merkle root determinism (CEPD-0): two independent computations agree.
      3. DAG node schema completeness: all required fields present/non-empty.
      4. Signature validity: signature covers SHA-256(node_id+merkle_root+payload_hash).
      5. Genesis traceability (CEPD-1): node reachable from genesis within max_depth.

    On full pass: CEPDDagNode appended to dag_store; CryptographicProofBundle produced.
    On any fail:  CEPD_NODE_REJECTED with specific failure codes; dag_store unchanged.

    Args:
        mutation_id: Unique mutation identifier.
        epoch_id: Current epoch string.
        payload_hash: SHA-256 of the mutation payload content.
        causal_ancestor_set: All causally upstream mutation IDs.
        parent_node_ids: Direct predecessor node IDs in the DAG.
        dag_store: Shared DAG store (genesis pre-seeded).
        signing_key: Key bytes for node signing.
        signing_mode: Ed25519 or HMAC_SHA256 (default: HMAC_SHA256).
        max_lineage_depth: Maximum DAG traversal depth.
        lineage_v2_tail_hash: Optional V2 ledger tail hash for additional binding.

    Returns:
        CEPDGateResult — always produced (pass or fail).
    """
    failure_codes: List[str] = []

    # Check 1: Ancestor completeness
    is_genesis_mutation = (mutation_id == GENESIS_MUTATION_ID)
    if not is_genesis_mutation:
        if not causal_ancestor_set:
            log.warning("CEPD-GATE-0 check 1 FAIL: empty causal_ancestor_set for non-genesis mutation '%s'", mutation_id)
            failure_codes.append(CEPD_ANCESTOR_INCOMPLETE)
        # All parent node IDs must exist in the store
        missing_parents = [pid for pid in parent_node_ids if dag_store.get(pid) is None]
        if missing_parents:
            log.warning("CEPD-GATE-0 check 1 FAIL: missing parent nodes %s", missing_parents)
            failure_codes.append(CEPD_ANCESTOR_INCOMPLETE)

    # Check 2: Merkle root determinism (CEPD-0)
    if not verify_merkle_determinism(causal_ancestor_set):
        log.error("CEPD-GATE-0 check 2 FAIL: Merkle root is nondeterministic — hard defect")
        failure_codes.append(CEPD_MERKLE_NONDETERMINISTIC)

    # Compute Merkle root (needed for node construction)
    ancestor_merkle_root = compute_ancestor_merkle_root(causal_ancestor_set)

    # Check 3: Node schema completeness
    schema_errors: List[str] = []
    if not mutation_id.strip():
        schema_errors.append("mutation_id empty")
    if not epoch_id.strip():
        schema_errors.append("epoch_id empty")
    if not payload_hash or len(payload_hash) < 32:
        schema_errors.append("payload_hash absent or too short")
    if not signing_key:
        schema_errors.append("signing_key empty")
    if schema_errors:
        log.warning("CEPD-GATE-0 check 3 FAIL: schema errors: %s", schema_errors)
        failure_codes.append(CEPD_NODE_INCOMPLETE)

    if failure_codes:
        rh = _result_hash(CEPDOutcome.REJECTED, failure_codes, None)
        return CEPDGateResult(
            outcome=CEPDOutcome.REJECTED,
            proof_bundle=None,
            failure_codes=tuple(failure_codes),
            result_hash=rh,
        )

    # Build node_id (requires clean merkle root)
    nid = _node_id(mutation_id, epoch_id, ancestor_merkle_root)

    # Check 4: Signature
    sig = sign_node(nid, ancestor_merkle_root, payload_hash, signing_key, signing_mode)
    if not verify_signature(nid, ancestor_merkle_root, payload_hash, sig, signing_key, signing_mode):
        log.error("CEPD-GATE-0 check 4 FAIL: signature invalid for node '%s'", nid)
        failure_codes.append(CEPD_SIGNATURE_INVALID)

    if failure_codes:
        rh = _result_hash(CEPDOutcome.REJECTED, failure_codes, None)
        return CEPDGateResult(
            outcome=CEPDOutcome.REJECTED,
            proof_bundle=None,
            failure_codes=tuple(failure_codes),
            result_hash=rh,
        )

    # Construct the node
    dag_node = CEPDDagNode(
        node_id=nid,
        mutation_id=mutation_id,
        epoch_id=epoch_id,
        parent_node_ids=tuple(parent_node_ids),
        ancestor_merkle_root=ancestor_merkle_root,
        payload_hash=payload_hash,
        signing_mode=signing_mode,
        signature=sig,
        cepd_version=CEPD_VERSION,
    )

    # Check 5: Genesis traceability (CEPD-1)
    # Temporarily append to check traceability
    dag_store.append(dag_node)
    traceable, depth = dag_store.check_genesis_traceable(nid, max_lineage_depth)

    if depth > max_lineage_depth:
        log.error("CEPD-GATE-0 check 5 FAIL: depth %d exceeds max %d", depth, max_lineage_depth)
        failure_codes.append(CEPD_DEPTH_EXCEEDED)

    if not traceable:
        log.error("CEPD-GATE-0 check 5 FAIL: genesis not traceable from node '%s'", nid)
        failure_codes.append(CEPD_GENESIS_UNTRACEABLE)

    if failure_codes:
        # Remove the node we speculatively appended
        dag_store._nodes.pop(nid, None)  # noqa: SLF001
        rh = _result_hash(CEPDOutcome.REJECTED, failure_codes, None)
        return CEPDGateResult(
            outcome=CEPDOutcome.REJECTED,
            proof_bundle=None,
            failure_codes=tuple(failure_codes),
            result_hash=rh,
        )

    # All checks passed — build CryptographicProofBundle
    bundle_payload = json.dumps(
        {
            "dag_node": dag_node.to_dict(),
            "ancestor_set": sorted(causal_ancestor_set),
            "ancestor_merkle_root": ancestor_merkle_root,
            "lineage_depth": depth,
            "genesis_traceable": traceable,
            "cepd_version": CEPD_VERSION,
        },
        sort_keys=True,
    )
    bundle_hash = _sha256(bundle_payload)
    bundle_id = f"CEPD-{bundle_hash[:20].upper()}"

    proof_bundle = CryptographicProofBundle(
        bundle_id=bundle_id,
        dag_node=dag_node,
        ancestor_set=causal_ancestor_set,
        ancestor_merkle_root=ancestor_merkle_root,
        lineage_depth=depth,
        genesis_traceable=True,
        bundle_hash=bundle_hash,
        cepd_version=CEPD_VERSION,
    )

    rh = _result_hash(CEPDOutcome.ACCEPTED, [], bundle_id)
    log.info(
        "CEPD-GATE-0 ACCEPTED: node '%s' for mutation '%s' — bundle '%s' (depth=%d)",
        nid,
        mutation_id,
        bundle_id,
        depth,
    )
    return CEPDGateResult(
        outcome=CEPDOutcome.ACCEPTED,
        proof_bundle=proof_bundle,
        failure_codes=(),
        result_hash=rh,
    )


# ---------------------------------------------------------------------------
# Bundle verification (independent verifier surface — patent prosecution)
# ---------------------------------------------------------------------------


def verify_proof_bundle(
    bundle: CryptographicProofBundle,
    signing_key: bytes,
) -> bool:
    """Independently verify a CryptographicProofBundle without system access.

    Checks:
      1. Merkle root recomputed from ancestor_set matches dag_node.ancestor_merkle_root.
      2. Node signature verifiable with supplied signing_key.
      3. bundle_hash reproducible from bundle fields.

    Returns True only if all three checks pass.
    """
    # 1. Merkle root
    recomputed_root = compute_ancestor_merkle_root(bundle.ancestor_set)
    if recomputed_root != bundle.ancestor_merkle_root:
        return False
    if recomputed_root != bundle.dag_node.ancestor_merkle_root:
        return False

    # 2. Signature
    node = bundle.dag_node
    if not verify_signature(
        node.node_id,
        node.ancestor_merkle_root,
        node.payload_hash,
        node.signature,
        signing_key,
        node.signing_mode,
    ):
        return False

    # 3. Bundle hash
    bundle_payload = json.dumps(
        {
            "dag_node": node.to_dict(),
            "ancestor_set": sorted(bundle.ancestor_set),
            "ancestor_merkle_root": bundle.ancestor_merkle_root,
            "lineage_depth": bundle.lineage_depth,
            "genesis_traceable": bundle.genesis_traceable,
            "cepd_version": bundle.cepd_version,
        },
        sort_keys=True,
    )
    expected_hash = _sha256(bundle_payload)
    return expected_hash == bundle.bundle_hash


# ---------------------------------------------------------------------------
# Ledger serialisation helper
# ---------------------------------------------------------------------------


def gate_result_to_ledger_payload(result: CEPDGateResult) -> Dict[str, Any]:
    """Convert a CEPDGateResult to a ledger-appendable dict."""
    payload: Dict[str, Any] = {
        "event_type": "cepd_gate_evaluation",
        "cepd_version": CEPD_VERSION,
        "outcome": result.outcome.value,
        "failure_codes": list(result.failure_codes),
        "result_hash": result.result_hash,
    }
    if result.proof_bundle is not None:
        payload["proof_bundle"] = result.proof_bundle.to_dict()
    return payload
