# SPDX-License-Identifier: Apache-2.0
"""Deterministic federation coherence validation before epoch bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
import os

from runtime import ROOT_DIR
from runtime.governance.deterministic_filesystem import read_file_deterministic
from runtime.governance.federation.coordination import FileBackedFederationRegistry, FederationPolicyExchange, FederationVote
from runtime.governance.federation.manifest import FederationManifest
from runtime.governance.federation.protocol import decode_handshake_request_envelope, encode_handshake_request_envelope
from runtime.governance.federation.transport import LocalFederationTransport
from runtime.governance.foundation.hashing import ZERO_HASH, sha256_prefixed_digest

DECISION_CONSENSUS = "CONSENSUS"
DECISION_LOCAL_OVERRIDE = "LOCAL_OVERRIDE"
DECISION_CONFLICT = "CONFLICT"
DECISION_SPLIT_BRAIN = "SPLIT_BRAIN"

RECOMMENDATION_PROCEED = "proceed"
RECOMMENDATION_ADVISORY = "advisory"
RECOMMENDATION_HALT = "halt"


@dataclass(frozen=True)
class CoherenceReport:
    local_peer_id: str
    local_policy_fingerprint: str
    peer_fingerprints: Dict[str, str]
    classifications: Dict[str, str]
    recommendation: str
    advisory: str
    hash_chain: List[Dict[str, str]]
    report_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "local_peer_id": self.local_peer_id,
            "local_policy_fingerprint": self.local_policy_fingerprint,
            "peer_fingerprints": {peer_id: self.peer_fingerprints[peer_id] for peer_id in sorted(self.peer_fingerprints)},
            "classifications": {peer_id: self.classifications[peer_id] for peer_id in sorted(self.classifications)},
            "recommendation": self.recommendation,
            "advisory": self.advisory,
            "hash_chain": [dict(item) for item in self.hash_chain],
            "report_hash": self.report_hash,
        }


class FederationCoherenceValidator:
    def __init__(self, *, registry: FileBackedFederationRegistry | None = None, transport: LocalFederationTransport | None = None) -> None:
        self.registry = registry or FileBackedFederationRegistry()
        self.transport = transport or LocalFederationTransport()

    def validate(self) -> CoherenceReport:
        local_peer_id = os.getenv("ADAAD_LOCAL_PEER_ID", "local-node")
        local_policy_version = os.getenv("ADAAD_POLICY_VERSION", "local")
        local_fingerprint = self._local_policy_fingerprint()

        peers = self.registry.peers()
        peer_fingerprints = {
            manifest.node_id: sha256_prefixed_digest(manifest.canonical_json())
            for manifest in sorted(peers, key=lambda item: item.node_id)
        }
        peer_versions = {manifest.node_id: manifest.law_version for manifest in sorted(peers, key=lambda item: item.node_id)}

        exchange = FederationPolicyExchange(
            local_peer_id=local_peer_id,
            local_policy_version=local_policy_version,
            local_manifest_digest=local_fingerprint,
            peer_versions=peer_versions,
            local_certificate={"fingerprint": local_fingerprint},
            peer_certificates={manifest.node_id: {"hmac_signature": manifest.hmac_signature} for manifest in peers},
        )

        votes = [
            FederationVote(
                peer_id=manifest.node_id,
                policy_version=manifest.law_version,
                manifest_digest=peer_fingerprints[manifest.node_id],
                decision="accept",
            )
            for manifest in sorted(peers, key=lambda item: item.node_id)
        ]

        classifications: Dict[str, str] = {}
        for manifest in sorted(peers, key=lambda item: item.node_id):
            self._exchange_policy_fingerprint(exchange=exchange, votes=votes, local_peer_id=local_peer_id, peer=manifest)
            classifications[manifest.node_id] = self._classify_peer(local_policy_version, local_fingerprint, manifest, peer_fingerprints[manifest.node_id])

        split_brain = self._detect_split_brain(local_policy_version, peers)
        if split_brain:
            for manifest in peers:
                classifications[manifest.node_id] = DECISION_SPLIT_BRAIN

        recommendation, advisory = self._recommendation(classifications)
        chain = self._hash_chain(local_peer_id, local_fingerprint, peer_fingerprints, classifications, recommendation, advisory)
        report_hash = chain[-1]["entry_hash"] if chain else ZERO_HASH
        return CoherenceReport(
            local_peer_id=local_peer_id,
            local_policy_fingerprint=local_fingerprint,
            peer_fingerprints=peer_fingerprints,
            classifications=classifications,
            recommendation=recommendation,
            advisory=advisory,
            hash_chain=chain,
            report_hash=report_hash,
        )

    def _local_policy_fingerprint(self) -> str:
        policy_path = ROOT_DIR / "runtime" / "governance" / "founders_law.json"
        return sha256_prefixed_digest(read_file_deterministic(policy_path))

    def _exchange_policy_fingerprint(
        self,
        *,
        exchange: FederationPolicyExchange,
        votes: List[FederationVote],
        local_peer_id: str,
        peer: FederationManifest,
    ) -> None:
        request_envelope = encode_handshake_request_envelope(
            message_id=f"coherence-{local_peer_id}-to-{peer.node_id}",
            exchange_id=f"coherence-{local_peer_id}",
            signature={"algorithm": "none", "key_id": local_peer_id, "value": "local"},
            exchange=exchange,
            votes=votes,
            phase="init",
        )
        transport_envelope = {
            "schema_id": "https://adaad.local/schemas/federation_transport_contract.v1.json",
            "protocol": "adaad.federation.transport",
            "protocol_version": "1.0",
            "envelope_id": f"coh-{local_peer_id}-{peer.node_id}",
            "source_peer_id": local_peer_id,
            "target_peer_id": peer.node_id,
            "sent_at_epoch": 0,
            "handshake": {
                "peer_id": local_peer_id,
                "policy_version": exchange.local_policy_version,
                "manifest_digest": exchange.local_manifest_digest,
                "decision": "accept",
                "is_local": True,
            },
        }
        self.transport.send_handshake(target_peer_id=peer.node_id, envelope=transport_envelope)
        self.transport.receive_handshake(local_peer_id=peer.node_id)
        decode_handshake_request_envelope(request_envelope)

    def _classify_peer(
        self,
        local_policy_version: str,
        local_fingerprint: str,
        peer: FederationManifest,
        peer_fingerprint: str,
    ) -> str:
        if peer.law_version == local_policy_version and peer_fingerprint == local_fingerprint:
            return DECISION_CONSENSUS
        if peer.law_version == local_policy_version and peer_fingerprint != local_fingerprint:
            return DECISION_LOCAL_OVERRIDE
        if peer.law_version != local_policy_version:
            return DECISION_CONFLICT
        return DECISION_LOCAL_OVERRIDE

    def _detect_split_brain(self, local_policy_version: str, peers: List[FederationManifest]) -> bool:
        peer_versions = {manifest.law_version for manifest in peers}
        return len(peer_versions) > 1 and local_policy_version not in peer_versions

    def _recommendation(self, classifications: Dict[str, str]) -> tuple[str, str]:
        values = list(classifications.values())
        if any(item == DECISION_SPLIT_BRAIN for item in values):
            return RECOMMENDATION_HALT, "split_brain_detected"
        if any(item == DECISION_CONFLICT for item in values):
            return RECOMMENDATION_ADVISORY, "policy_conflict_detected"
        if any(item == DECISION_LOCAL_OVERRIDE for item in values):
            return RECOMMENDATION_ADVISORY, "local_override_observed"
        return RECOMMENDATION_PROCEED, "federation_consensus"

    def _hash_chain(
        self,
        local_peer_id: str,
        local_fingerprint: str,
        peer_fingerprints: Dict[str, str],
        classifications: Dict[str, str],
        recommendation: str,
        advisory: str,
    ) -> List[Dict[str, str]]:
        chain: List[Dict[str, str]] = []
        prev_hash = ZERO_HASH
        rows: List[Dict[str, str]] = [
            {"peer_id": local_peer_id, "fingerprint": local_fingerprint, "classification": DECISION_CONSENSUS}
        ]
        for peer_id in sorted(peer_fingerprints):
            rows.append(
                {
                    "peer_id": peer_id,
                    "fingerprint": peer_fingerprints[peer_id],
                    "classification": classifications.get(peer_id, DECISION_CONFLICT),
                }
            )
        rows.append({"peer_id": "recommendation", "fingerprint": recommendation, "classification": advisory})

        for row in rows:
            entry_hash = sha256_prefixed_digest({"prev_hash": prev_hash, "entry": row})
            chain.append({"prev_hash": prev_hash, "entry_hash": entry_hash})
            prev_hash = entry_hash
        return chain


__all__ = [
    "CoherenceReport",
    "FederationCoherenceValidator",
    "DECISION_CONFLICT",
    "DECISION_CONSENSUS",
    "DECISION_LOCAL_OVERRIDE",
    "DECISION_SPLIT_BRAIN",
    "RECOMMENDATION_ADVISORY",
    "RECOMMENDATION_HALT",
    "RECOMMENDATION_PROCEED",
]
