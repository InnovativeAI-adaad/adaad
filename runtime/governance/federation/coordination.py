# SPDX-License-Identifier: Apache-2.0
"""Deterministic federation coordination and conflict-resolution helpers.

Mutation rationale:
- Federation negotiation and reconciliation outcomes are modeled as immutable,
  canonicalized payloads so that event digests and replay outcomes stay deterministic.
- File-backed manifest exchange supports air-gapped deployments by keeping transport
  out-of-scope and relying only on local filesystem synchronization.
- Mutation lock files provide a conservative, deterministic coordination primitive
  to avoid concurrent intent execution.

Expected invariants:
- Peer ordering and vote tallying are stable for identical inputs.
- Governance precedence is explicit and fail-closed when local governance diverges.
- Federation decisions persisted to the lineage ledger are append-only and auditable.
- Stale manifests are excluded from compatibility checks after configured TTL expiry.
- Mutation locks are acquired at-most-once for an intent while lock TTL is valid.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
from time import time
from typing import TYPE_CHECKING, Dict, Iterable, List, Literal, Optional

from runtime.governance.federation.manifest import FederationManifest

if TYPE_CHECKING:
    from runtime.evolution.lineage_v2 import LineageLedgerV2

DECISION_CLASS_CONSENSUS = "consensus"
DECISION_CLASS_QUORUM = "quorum"
DECISION_CLASS_CONFLICT = "conflict"
DECISION_CLASS_REJECTED = "rejected"
DECISION_CLASS_LOCAL_OVERRIDE = "local_override"

POLICY_PRECEDENCE_LOCAL = "local"
POLICY_PRECEDENCE_FEDERATED = "federated"
POLICY_PRECEDENCE_BOTH = "both"

COMPATIBILITY_FULL = "full"
COMPATIBILITY_DOWNLEVEL = "downlevel"
COMPATIBILITY_INCOMPATIBLE = "incompatible"

_DEFAULT_MANIFEST_DIR = Path("runtime/governance/federation/manifests")
_DEFAULT_LOCK_DIR = Path("runtime/governance/federation/manifests")


@dataclass(frozen=True)
class FederationVote:
    peer_id: str
    policy_version: str
    manifest_digest: str
    decision: Literal["accept", "reject"] = "accept"


@dataclass(frozen=True)
class FederationPolicyExchange:
    local_peer_id: str
    local_policy_version: str
    local_manifest_digest: str
    peer_versions: Dict[str, str] = field(default_factory=dict)
    local_certificate: Dict[str, str] = field(default_factory=dict)
    peer_certificates: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def canonical_payload(self) -> Dict[str, object]:
        return {
            "local_peer_id": self.local_peer_id,
            "local_policy_version": self.local_policy_version,
            "local_manifest_digest": self.local_manifest_digest,
            "local_certificate": {key: self.local_certificate[key] for key in sorted(self.local_certificate)},
            "peer_versions": {key: self.peer_versions[key] for key in sorted(self.peer_versions)},
            "peer_certificates": {
                peer_id: {
                    cert_key: self.peer_certificates[peer_id][cert_key]
                    for cert_key in sorted(self.peer_certificates[peer_id])
                }
                for peer_id in sorted(self.peer_certificates)
            },
        }

    def exchange_digest(self) -> str:
        encoded = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "sha256:" + sha256(encoded).hexdigest()


@dataclass(frozen=True)
class FederationCoordinationResult:
    decision: FederationDecision
    federated_passed: bool
    divergence_class: str
    fail_closed: bool
    emitted_events: List[Dict[str, object]]


@dataclass(frozen=True)
class LockAcquisitionResult:
    acquired: bool
    lock_path: Path


def _now_epoch_seconds() -> int:
    return int(time())


def _manifest_ttl_seconds() -> int:
    return int(os.getenv("ADAAD_FEDERATION_MANIFEST_TTL", "300"))


def _lock_ttl_seconds() -> int:
    return int(os.getenv("ADAAD_FEDERATION_LOCK_TTL", "120"))


def _federation_enabled() -> bool:
    return os.getenv("ADAAD_FEDERATION_ENABLED", "false").strip().lower() == "true"


def _read_json_file(path: Path) -> Optional[Dict[str, object]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


class FileBackedFederationRegistry:
    """Filesystem-backed peer manifest registry for air-gapped federation."""

    def __init__(self, manifest_dir: Path = _DEFAULT_MANIFEST_DIR, ttl_seconds: Optional[int] = None) -> None:
        self._manifest_dir = manifest_dir
        self._ttl_seconds = _manifest_ttl_seconds() if ttl_seconds is None else max(0, ttl_seconds)

    def peers(self) -> List[FederationManifest]:
        if not _federation_enabled():
            return []

        manifests: List[FederationManifest] = []
        if not self._manifest_dir.exists():
            return manifests

        now = _now_epoch_seconds()
        signing_key = FederationManifest.deterministic_key_from_env()
        for path in sorted(self._manifest_dir.glob("*.json")):
            payload = _read_json_file(path)
            if payload is None:
                continue
            manifest = FederationManifest.from_dict(payload)
            written_at = int(payload.get("written_at", 0))
            if now - written_at > self._ttl_seconds:
                continue
            if not manifest.verify_manifest(signing_key):
                continue
            manifests.append(manifest)
        return manifests


def classify_manifest_compatibility(local: FederationManifest, peer: FederationManifest) -> str:
    if local.trust_mode != peer.trust_mode:
        return COMPATIBILITY_INCOMPATIBLE
    if local.law_version == peer.law_version:
        return COMPATIBILITY_FULL
    local_base = local.law_version.split(".")[0]
    peer_base = peer.law_version.split(".")[0]
    if local_base == peer_base:
        return COMPATIBILITY_DOWNLEVEL
    return COMPATIBILITY_INCOMPATIBLE


def _lock_path(intent_id: str, lock_dir: Path = _DEFAULT_LOCK_DIR) -> Path:
    return lock_dir / f"mutation_lock_{intent_id}.lock"


def _lock_is_stale(path: Path, ttl_seconds: int) -> bool:
    payload = _read_json_file(path)
    if payload is None:
        return True
    acquired_at = int(payload.get("acquired_at", 0))
    return _now_epoch_seconds() - acquired_at > ttl_seconds


def acquire_mutation_lock(intent_id: str, lock_dir: Path = _DEFAULT_LOCK_DIR) -> LockAcquisitionResult:
    """Acquire a file lock using atomic create semantics where available.

    Invariant: a valid non-stale lock file for the same intent_id prevents acquisition.
    """

    ttl_seconds = _lock_ttl_seconds()
    lock_dir.mkdir(parents=True, exist_ok=True)
    path = _lock_path(intent_id, lock_dir)

    if path.exists() and not _lock_is_stale(path, ttl_seconds):
        return LockAcquisitionResult(acquired=False, lock_path=path)
    if path.exists() and _lock_is_stale(path, ttl_seconds):
        path.unlink(missing_ok=True)

    payload = {"intent_id": intent_id, "acquired_at": _now_epoch_seconds()}
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return LockAcquisitionResult(acquired=True, lock_path=path)
    except FileExistsError:
        return LockAcquisitionResult(acquired=False, lock_path=path)


def release_mutation_lock(intent_id: str, lock_dir: Path = _DEFAULT_LOCK_DIR) -> bool:
    path = _lock_path(intent_id, lock_dir)
    if not path.exists():
        return False
    path.unlink(missing_ok=True)
    return True


def _vote_payload(votes: Iterable[FederationVote]) -> List[Dict[str, str]]:
    rows = [
        {
            "peer_id": vote.peer_id,
            "policy_version": vote.policy_version,
            "manifest_digest": vote.manifest_digest,
            "decision": vote.decision,
        }
        for vote in votes
    ]
    return sorted(rows, key=lambda item: (item["peer_id"], item["policy_version"], item["manifest_digest"], item["decision"]))


def _vote_digest(votes: Iterable[FederationVote]) -> str:
    encoded = json.dumps(_vote_payload(votes), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def evaluate_federation_decision(
    exchange: FederationPolicyExchange,
    votes: List[FederationVote],
    *,
    quorum_size: int,
) -> FederationDecision:
    """Evaluate deterministic quorum/consensus decision from local + peer votes."""
    tallies: Dict[str, int] = {exchange.local_policy_version: 1}
    manifest_digests: Dict[str, str] = {exchange.local_peer_id: exchange.local_manifest_digest}

    for vote in sorted(votes, key=lambda item: item.peer_id):
        manifest_digests[vote.peer_id] = vote.manifest_digest
        if vote.decision != "accept":
            continue
        tallies[vote.policy_version] = tallies.get(vote.policy_version, 0) + 1

    sorted_versions = sorted(tallies.items(), key=lambda item: (-item[1], item[0]))
    selected_policy_version, selected_count = sorted_versions[0]
    consensus = len(sorted_versions) == 1
    has_quorum = selected_count >= quorum_size

    if consensus and has_quorum:
        decision_class = DECISION_CLASS_CONSENSUS
        reconciliation_actions = ["bind_policy_version"]
    elif has_quorum:
        decision_class = DECISION_CLASS_QUORUM
        reconciliation_actions = ["stage_majority_policy", "request_minor_peer_reconciliation"]
    elif len(sorted_versions) > 1:
        decision_class = DECISION_CLASS_CONFLICT
        selected_policy_version = exchange.local_policy_version
        reconciliation_actions = ["freeze_federated_upgrade", "require_local_governance_review"]
    else:
        decision_class = DECISION_CLASS_REJECTED
        reconciliation_actions = ["reject_federated_policy_update"]

    return FederationDecision(
        decision_class=decision_class,
        selected_policy_version=selected_policy_version,
        peer_ids=sorted(manifest_digests),
        manifest_digests={peer_id: manifest_digests[peer_id] for peer_id in sorted(manifest_digests)},
        reconciliation_actions=reconciliation_actions,
        quorum_size=max(1, quorum_size),
        vote_digest=_vote_digest(votes),
    )


@dataclass(frozen=True)
class FederationDecision:
    decision_class: str
    selected_policy_version: str
    peer_ids: List[str]
    manifest_digests: Dict[str, str]
    reconciliation_actions: List[str]
    quorum_size: int
    vote_digest: str


def run_coordination_cycle(peer_handshakes: list[dict]) -> FederationCoordinationResult:
    """Single deterministic entrypoint for quorum coordination from peer handshakes."""
    sorted_handshakes = sorted(
        [dict(handshake) for handshake in peer_handshakes],
        key=lambda row: (str(row.get("peer_id", "")), str(row.get("policy_version", "")), str(row.get("manifest_digest", ""))),
    )

    local_handshake = next((row for row in sorted_handshakes if bool(row.get("is_local"))), None)
    if local_handshake is None:
        raise ValueError("local_handshake_missing")

    exchange = FederationPolicyExchange(
        local_peer_id=str(local_handshake["peer_id"]),
        local_policy_version=str(local_handshake["policy_version"]),
        local_manifest_digest=str(local_handshake["manifest_digest"]),
        peer_versions={
            str(row["peer_id"]): str(row["policy_version"])
            for row in sorted_handshakes
            if str(row["peer_id"]) != str(local_handshake["peer_id"])
        },
    )
    votes = [
        FederationVote(
            peer_id=str(row["peer_id"]),
            policy_version=str(row["policy_version"]),
            manifest_digest=str(row["manifest_digest"]),
            decision="accept" if row.get("decision", "accept") == "accept" else "reject",
        )
        for row in sorted_handshakes
        if str(row["peer_id"]) != str(local_handshake["peer_id"])
    ]
    decision = evaluate_federation_decision(exchange, votes, quorum_size=max(1, len(sorted_handshakes)))

    mismatched_peers = [
        vote.peer_id
        for vote in votes
        if vote.policy_version != exchange.local_policy_version or vote.manifest_digest != exchange.local_manifest_digest
    ]
    divergence_class = "none" if not mismatched_peers else "drift_federated_split_brain"
    fail_closed = divergence_class != "none"

    emitted_events: List[Dict[str, object]]
    if not fail_closed and decision.decision_class in {DECISION_CLASS_CONSENSUS, DECISION_CLASS_QUORUM}:
        emitted_events = [
            {
                "event_type": "federation_verified",
                "decision_class": decision.decision_class,
                "peer_count": len(sorted_handshakes),
            }
        ]
    else:
        emitted_events = [
            {
                "event_type": "federation_divergence_detected",
                "decision_class": decision.decision_class,
                "divergence_class": divergence_class,
                "fail_closed": True,
                "mismatched_peers": mismatched_peers,
            }
        ]

    return FederationCoordinationResult(
        decision=decision,
        federated_passed=not fail_closed and decision.decision_class in {DECISION_CLASS_CONSENSUS, DECISION_CLASS_QUORUM},
        divergence_class=divergence_class,
        fail_closed=fail_closed,
        emitted_events=emitted_events,
    )


def resolve_governance_precedence(
    *,
    local_passed: bool,
    federated_passed: bool,
    policy_precedence: str = POLICY_PRECEDENCE_BOTH,
) -> Dict[str, object]:
    """Resolve final replay/governance pass decision with explicit precedence rules."""
    if policy_precedence == POLICY_PRECEDENCE_LOCAL:
        final_passed = local_passed
        source = POLICY_PRECEDENCE_LOCAL
    elif policy_precedence == POLICY_PRECEDENCE_FEDERATED:
        final_passed = federated_passed
        source = POLICY_PRECEDENCE_FEDERATED
    else:
        final_passed = local_passed and federated_passed
        source = POLICY_PRECEDENCE_BOTH

    if not local_passed and federated_passed:
        decision_class = DECISION_CLASS_LOCAL_OVERRIDE
    elif local_passed and not federated_passed:
        decision_class = DECISION_CLASS_CONFLICT
    elif final_passed:
        decision_class = DECISION_CLASS_CONSENSUS
    else:
        decision_class = DECISION_CLASS_REJECTED

    return {
        "passed": final_passed,
        "decision_class": decision_class,
        "precedence_source": source,
        "local_passed": local_passed,
        "federated_passed": federated_passed,
    }


def persist_federation_decision(
    ledger: "LineageLedgerV2",
    *,
    epoch_id: str,
    exchange: FederationPolicyExchange,
    decision: FederationDecision,
) -> Dict[str, object]:
    payload = {
        "epoch_id": epoch_id,
        "local_peer_id": exchange.local_peer_id,
        "exchange_digest": exchange.exchange_digest(),
        "peer_ids": decision.peer_ids,
        "manifest_digests": decision.manifest_digests,
        "decision_class": decision.decision_class,
        "selected_policy_version": decision.selected_policy_version,
        "quorum_size": decision.quorum_size,
        "vote_digest": decision.vote_digest,
        "reconciliation_actions": decision.reconciliation_actions,
    }
    return ledger.append_event("FederationDecisionEvent", payload)


__all__ = [
    "COMPATIBILITY_DOWNLEVEL",
    "COMPATIBILITY_FULL",
    "COMPATIBILITY_INCOMPATIBLE",
    "DECISION_CLASS_CONFLICT",
    "DECISION_CLASS_CONSENSUS",
    "DECISION_CLASS_LOCAL_OVERRIDE",
    "DECISION_CLASS_QUORUM",
    "DECISION_CLASS_REJECTED",
    "POLICY_PRECEDENCE_BOTH",
    "POLICY_PRECEDENCE_FEDERATED",
    "POLICY_PRECEDENCE_LOCAL",
    "FederationCoordinationResult",
    "FederationDecision",
    "FederationPolicyExchange",
    "FederationVote",
    "FileBackedFederationRegistry",
    "LockAcquisitionResult",
    "acquire_mutation_lock",
    "classify_manifest_compatibility",
    "evaluate_federation_decision",
    "persist_federation_decision",
    "release_mutation_lock",
    "resolve_governance_precedence",
    "run_coordination_cycle",
]
