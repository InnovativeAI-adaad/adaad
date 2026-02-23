# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

from runtime.governance.federation.coordination import (
    COMPATIBILITY_DOWNLEVEL,
    COMPATIBILITY_FULL,
    COMPATIBILITY_INCOMPATIBLE,
    DECISION_CLASS_SPLIT_BRAIN,
    FileBackedFederationRegistry,
    acquire_mutation_lock,
    classify_manifest_compatibility,
    run_coordination_cycle,
    release_mutation_lock,
)
from runtime.governance.federation.manifest import FederationManifest


def _write_manifest(path: Path, manifest: FederationManifest, written_at: int) -> None:
    payload = manifest.to_dict()
    payload["written_at"] = written_at
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def test_manifest_sign_and_verify_round_trip(monkeypatch) -> None:
    monkeypatch.setenv("ADAAD_FEDERATION_MANIFEST_HMAC_KEY", "test-key")
    manifest = FederationManifest(
        node_id="node-a",
        law_version="v0.70.0",
        trust_mode="strict",
        epoch_id="epoch-1",
        active_modules=["governance", "federation"],
    )

    signed = manifest.sign_manifest(FederationManifest.deterministic_key_from_env())

    assert signed.verify_manifest("test-key")
    assert not signed.verify_manifest("wrong-key")


def test_file_backed_registry_filters_stale_and_invalid(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ADAAD_FEDERATION_ENABLED", "true")
    monkeypatch.setenv("ADAAD_FEDERATION_MANIFEST_HMAC_KEY", "test-key")

    now = 10_000
    monkeypatch.setattr("runtime.governance.federation.coordination._now_epoch_seconds", lambda: now)

    fresh = FederationManifest("node-a", "v0.70.0", "strict", "epoch-1", ["federation"]).sign_manifest("test-key")
    stale = FederationManifest("node-b", "v0.70.0", "strict", "epoch-1", ["federation"]).sign_manifest("test-key")
    bad_sig = FederationManifest("node-c", "v0.70.0", "strict", "epoch-1", ["federation"]).sign_manifest("other-key")

    _write_manifest(tmp_path / "fresh.json", fresh, written_at=9_950)
    _write_manifest(tmp_path / "stale.json", stale, written_at=9_000)
    _write_manifest(tmp_path / "bad.json", bad_sig, written_at=9_990)

    registry = FileBackedFederationRegistry(tmp_path, ttl_seconds=60)
    peers = registry.peers()

    assert [peer.node_id for peer in peers] == ["node-a"]


def test_registry_respects_air_gapped_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ADAAD_FEDERATION_ENABLED", raising=False)
    signed = FederationManifest("node-a", "v0.70.0", "strict", "epoch-1", ["federation"]).sign_manifest("k")
    _write_manifest(tmp_path / "peer.json", signed, written_at=1)

    assert FileBackedFederationRegistry(tmp_path, ttl_seconds=999999).peers() == []


def test_compatibility_classification() -> None:
    local = FederationManifest("local", "v0.70.0", "strict", "e", ["f"])
    same = FederationManifest("peer-a", "v0.70.0", "strict", "e", ["f"])
    downlevel = FederationManifest("peer-b", "v0.71.1", "strict", "e", ["f"])
    incompatible = FederationManifest("peer-c", "v1.0.0", "permissive", "e", ["f"])

    assert classify_manifest_compatibility(local, same) == COMPATIBILITY_FULL
    assert classify_manifest_compatibility(local, downlevel) == COMPATIBILITY_DOWNLEVEL
    assert classify_manifest_compatibility(local, incompatible) == COMPATIBILITY_INCOMPATIBLE


def test_mutation_lock_contention_and_release(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ADAAD_FEDERATION_LOCK_TTL", "30")
    monkeypatch.setattr("runtime.governance.federation.coordination._now_epoch_seconds", lambda: 100)

    first = acquire_mutation_lock("intent-1", lock_dir=tmp_path)
    second = acquire_mutation_lock("intent-1", lock_dir=tmp_path)

    assert first.acquired
    assert not second.acquired

    assert release_mutation_lock("intent-1", lock_dir=tmp_path)
    third = acquire_mutation_lock("intent-1", lock_dir=tmp_path)
    assert third.acquired


def test_mutation_lock_ttl_allows_reacquire(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ADAAD_FEDERATION_LOCK_TTL", "5")

    monkeypatch.setattr("runtime.governance.federation.coordination._now_epoch_seconds", lambda: 10)
    assert acquire_mutation_lock("intent-expire", lock_dir=tmp_path).acquired

    monkeypatch.setattr("runtime.governance.federation.coordination._now_epoch_seconds", lambda: 20)
    assert acquire_mutation_lock("intent-expire", lock_dir=tmp_path).acquired


def test_split_brain_escalation_behavior() -> None:
    result = run_coordination_cycle(
        [
            {"peer_id": "node-a", "policy_version": "2.0.0", "manifest_digest": "sha256:" + ("a" * 64), "is_local": True},
            {"peer_id": "node-b", "policy_version": "2.1.0", "manifest_digest": "sha256:" + ("b" * 64), "decision": "accept"},
            {"peer_id": "node-c", "policy_version": "2.0.0", "manifest_digest": "sha256:" + ("c" * 64), "decision": "accept"},
            {"peer_id": "node-d", "policy_version": "2.1.0", "manifest_digest": "sha256:" + ("d" * 64), "decision": "accept"},
        ]
    )

    assert result.decision.decision_class == DECISION_CLASS_SPLIT_BRAIN
    assert result.fail_closed
    assert "escalate_split_brain_review" in result.decision.reconciliation_actions
