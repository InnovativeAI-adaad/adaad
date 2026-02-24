# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from runtime.governance.federation.coherence_validator import (
    DECISION_CONFLICT,
    DECISION_CONSENSUS,
    DECISION_LOCAL_OVERRIDE,
    DECISION_SPLIT_BRAIN,
    FederationCoherenceValidator,
    RECOMMENDATION_ADVISORY,
    RECOMMENDATION_HALT,
    RECOMMENDATION_PROCEED,
)
from runtime.governance.federation.manifest import FederationManifest
from runtime.governance.foundation.hashing import sha256_prefixed_digest


class _Registry:
    def __init__(self, peers):
        self._peers = peers

    def peers(self):
        return list(self._peers)


def _manifest(node_id: str, law_version: str, *, modules: list[str] | None = None) -> FederationManifest:
    return FederationManifest(
        node_id=node_id,
        law_version=law_version,
        trust_mode="strict",
        epoch_id="epoch-1",
        active_modules=modules or ["federation"],
    )


def test_consensus_recommendation_and_hash_chain(monkeypatch) -> None:
    monkeypatch.setenv("ADAAD_LOCAL_PEER_ID", "node-a")
    monkeypatch.setenv("ADAAD_POLICY_VERSION", "2.0.0")
    peer = _manifest("node-b", "2.0.0")
    peer_fp = sha256_prefixed_digest(peer.canonical_json())
    monkeypatch.setattr(
        "runtime.governance.federation.coherence_validator.FederationCoherenceValidator._local_policy_fingerprint",
        lambda _self: peer_fp,
    )
    validator = FederationCoherenceValidator(registry=_Registry([peer]))

    report = validator.validate()

    assert report.classifications["node-b"] == DECISION_CONSENSUS
    assert report.recommendation == RECOMMENDATION_PROCEED
    assert report.hash_chain[0]["prev_hash"].startswith("sha256:")
    assert report.report_hash == report.hash_chain[-1]["entry_hash"]


def test_split_brain_halts(monkeypatch) -> None:
    monkeypatch.setenv("ADAAD_LOCAL_PEER_ID", "node-a")
    monkeypatch.setenv("ADAAD_POLICY_VERSION", "9.9.9")
    monkeypatch.setattr(
        "runtime.governance.federation.coherence_validator.FederationCoherenceValidator._local_policy_fingerprint",
        lambda _self: "sha256:" + ("a" * 64),
    )
    validator = FederationCoherenceValidator(registry=_Registry([_manifest("node-b", "2.0.0"), _manifest("node-c", "3.0.0")]))

    report = validator.validate()

    assert report.classifications["node-b"] == DECISION_SPLIT_BRAIN
    assert report.classifications["node-c"] == DECISION_SPLIT_BRAIN
    assert report.recommendation == RECOMMENDATION_HALT


def test_classification_matrix(monkeypatch) -> None:
    monkeypatch.setenv("ADAAD_POLICY_VERSION", "2.0.0")
    local_fp = "sha256:" + ("1" * 64)
    monkeypatch.setattr(
        "runtime.governance.federation.coherence_validator.FederationCoherenceValidator._local_policy_fingerprint",
        lambda _self: local_fp,
    )
    validator = FederationCoherenceValidator(registry=_Registry([]))

    same = _manifest("node-x", "2.0.0")
    override = _manifest("node-y", "2.0.0", modules=["different"])
    conflict = _manifest("node-z", "2.1.0")

    assert validator._classify_peer("2.0.0", local_fp, same, local_fp) == DECISION_CONSENSUS
    assert validator._classify_peer("2.0.0", local_fp, override, "sha256:" + ("2" * 64)) == DECISION_LOCAL_OVERRIDE
    assert validator._classify_peer("2.0.0", local_fp, conflict, local_fp) == DECISION_CONFLICT
    assert validator._recommendation({"a": DECISION_LOCAL_OVERRIDE})[0] == RECOMMENDATION_ADVISORY
    assert validator._recommendation({"a": DECISION_CONSENSUS})[0] == RECOMMENDATION_PROCEED
