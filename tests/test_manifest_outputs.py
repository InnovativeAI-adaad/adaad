# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import pytest
pytestmark = pytest.mark.regression_standard

import json
from pathlib import Path

from app.dream_mode import DreamMode
from runtime.evolution.replay_service import ReplayVerificationService
from runtime.governance.foundation import SeededDeterminismProvider


class _Fitness:
    def to_dict(self) -> dict:
        return {"score": 0.95, "constitution_ok": True}


def test_write_dream_manifest_creates_expected_file(tmp_path: Path) -> None:
    dream = DreamMode(
        tmp_path / "agents",
        tmp_path / "lineage",
        replay_mode="audit",
        recovery_tier="advisory",
        provider=SeededDeterminismProvider(seed="manifest"),
    )
    staged_path = tmp_path / "lineage" / "_staging" / "candidate"
    staged_path.mkdir(parents=True)

    manifest_path = dream.write_dream_manifest(
        agent_id="agent.alpha",
        epoch_id="epoch-42",
        bundle_id="dream",
        staged_path=staged_path,
        fitness=_Fitness(),
    )

    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["agent_id"] == "agent.alpha"
    assert payload["epoch_id"] == "epoch-42"
    assert payload["bundle_id"] == "dream"
    assert payload["staged_path"] == str(staged_path)
    assert payload["replay_mode"] == "audit"
    assert payload["recovery_tier"] == "advisory"
    assert payload["fitness"]["score"] == 0.95


def test_write_replay_manifest_creates_expected_file(tmp_path: Path) -> None:
    service = ReplayVerificationService(manifests_dir=tmp_path / "adaad" / "replay" / "manifests")
    manifest = {
        "replay_started_at": "2026-02-13T10:00:00Z",
        "replay_finished_at": "2026-02-13T10:01:00Z",
        "evidence_items_consumed": ["epoch-1"],
        "lineage_chain": [{"epoch_id": "epoch-1", "decision": "match", "passed": True, "replay_score": 1.0}],
        "reconstructed_state_hash": "sha256:" + ("1" * 64),
        "divergence": {"class": "none", "indicators": [], "halted": False},
        "algorithm": "hmac-sha256",
        "key_id": "proof-key",
        "signature": "sha256:" + ("2" * 64),
    }

    manifest_path = service.write_replay_manifest(manifest)

    assert Path(manifest_path).exists()
    assert Path(manifest_path).parent.name == "manifests"
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    assert payload["replay_started_at"] == "2026-02-13T10:00:00Z"
    assert payload["replay_finished_at"] == "2026-02-13T10:01:00Z"
    assert payload["divergence"]["class"] == "none"
    assert payload["algorithm"] == "hmac-sha256"
    assert payload["key_id"] == "proof-key"
