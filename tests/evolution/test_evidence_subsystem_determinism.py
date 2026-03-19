# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.evolution.evidence_bundle import EvidenceBundleBuilder
from runtime.evolution.lineage_v2 import LineageLedgerV2
from runtime.governance.foundation import canonical_json

pytestmark = pytest.mark.regression_standard


def _write_sandbox_evidence(path: Path, *, epoch_id: str, bundle_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "payload": {
            "epoch_id": epoch_id,
            "bundle_id": bundle_id,
            "evidence_hash": "sha256:evidence-a",
            "manifest_hash": "sha256:manifest-a",
            "policy_hash": "sha256:policy-a",
            "manifest": {
                "epoch_id": epoch_id,
                "bundle_id": bundle_id,
            },
        },
        "prev_hash": "sha256:0",
        "hash": "sha256:entry-a",
    }
    path.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")


def _build_bundle_from_synthetic_events(run_dir: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setenv("ADAAD_EVIDENCE_BUNDLE_SIGNING_KEY", "phase65-deterministic-signing-key")
    monkeypatch.setenv("ADAAD_EVIDENCE_BUNDLE_KEY_ID", "forensics-dev")
    monkeypatch.setenv("ADAAD_RUNTIME_BUILD_HASH", "sha256:runtime-build-fixed")
    monkeypatch.setenv("ADAAD_CONTAINER_HASH", "sha256:container-fixed")

    ledger = LineageLedgerV2(ledger_path=run_dir / "lineage_v2.jsonl")
    ledger.append_event("EpochStartEvent", {"epoch_id": "epoch-synth-001", "state": {"governance_mode": "strict"}})
    ledger.append_event(
        "GovernanceDecisionEvent",
        {
            "epoch_id": "epoch-synth-001",
            "decision_id": "gov-001",
            "rule": "lineage_continuity",
            "result": "pass",
        },
    )
    ledger.append_bundle_with_digest(
        "epoch-synth-001",
        {
            "bundle_id": "bundle-synth-001",
            "impact": 0.2,
            "risk_tier": "low",
            "certificate": {
                "bundle_id": "bundle-synth-001",
                "agent_id": "agent-synth",
                "strategy_snapshot_hash": "sha256:strategy-snapshot-a",
            },
            "strategy_set": ["mutation.safe_refactor"],
        },
    )
    ledger.append_event("EpochEndEvent", {"epoch_id": "epoch-synth-001", "state": {"accepted": 1, "rejected": 0}})

    sandbox_path = run_dir / "sandbox_evidence.jsonl"
    _write_sandbox_evidence(sandbox_path, epoch_id="epoch-synth-001", bundle_id="bundle-synth-001")

    builder = EvidenceBundleBuilder(
        ledger=ledger,
        sandbox_evidence_path=sandbox_path,
        export_dir=run_dir / "exports",
        schema_path=Path("schemas/evidence_bundle.v1.json"),
    )
    return builder.build_bundle(epoch_start="epoch-synth-001", persist=False)


def test_evidence_subsystem_outputs_are_identical_across_independent_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _build_bundle_from_synthetic_events(tmp_path / "run_a", monkeypatch)
    second = _build_bundle_from_synthetic_events(tmp_path / "run_b", monkeypatch)
    normalized_first = dict(first)
    normalized_second = dict(second)
    normalized_first["export_metadata"] = dict(first["export_metadata"])
    normalized_second["export_metadata"] = dict(second["export_metadata"])
    normalized_first["export_metadata"].pop("path", None)
    normalized_second["export_metadata"].pop("path", None)

    assert first["export_metadata"]["digest"] == second["export_metadata"]["digest"]
    assert first["export_metadata"]["signer"]["signed_digest"] == second["export_metadata"]["signer"]["signed_digest"]
    assert first["export_metadata"]["signer"]["signature"] == second["export_metadata"]["signer"]["signature"]
    assert first["lineage_anchors"] == second["lineage_anchors"]
    assert first["bundle_index"] == second["bundle_index"]
    assert canonical_json(normalized_first) == canonical_json(normalized_second)
