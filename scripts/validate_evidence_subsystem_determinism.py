#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed determinism validation for the evidence orchestration subsystem."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from runtime.evolution.evidence_bundle import EvidenceBundleBuilder
from runtime.evolution.lineage_v2 import LineageLedgerV2
from runtime.governance.foundation import canonical_json


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


def _build_bundle(run_dir: Path) -> dict:
    ledger = LineageLedgerV2(ledger_path=run_dir / "lineage_v2.jsonl")
    epoch_id = "epoch-synth-001"
    bundle_id = "bundle-synth-001"

    ledger.append_event("EpochStartEvent", {"epoch_id": epoch_id, "state": {"governance_mode": "strict"}})
    ledger.append_event(
        "GovernanceDecisionEvent",
        {
            "epoch_id": epoch_id,
            "decision_id": "gov-001",
            "rule": "lineage_continuity",
            "result": "pass",
        },
    )
    ledger.append_bundle_with_digest(
        epoch_id,
        {
            "bundle_id": bundle_id,
            "impact": 0.2,
            "risk_tier": "low",
            "certificate": {
                "bundle_id": bundle_id,
                "agent_id": "agent-synth",
                "strategy_snapshot_hash": "sha256:strategy-snapshot-a",
            },
            "strategy_set": ["mutation.safe_refactor"],
        },
    )
    ledger.append_event("EpochEndEvent", {"epoch_id": epoch_id, "state": {"accepted": 1, "rejected": 0}})

    sandbox_path = run_dir / "sandbox_evidence.jsonl"
    _write_sandbox_evidence(sandbox_path, epoch_id=epoch_id, bundle_id=bundle_id)

    builder = EvidenceBundleBuilder(
        ledger=ledger,
        sandbox_evidence_path=sandbox_path,
        export_dir=run_dir / "exports",
        schema_path=Path("schemas/evidence_bundle.v1.json"),
    )
    return builder.build_bundle(epoch_start=epoch_id, persist=False)


def _set_deterministic_env() -> None:
    os.environ.setdefault("ADAAD_EVIDENCE_BUNDLE_SIGNING_KEY", "phase65-deterministic-signing-key")
    os.environ.setdefault("ADAAD_EVIDENCE_BUNDLE_KEY_ID", "forensics-dev")
    os.environ.setdefault("ADAAD_RUNTIME_BUILD_HASH", "sha256:runtime-build-fixed")
    os.environ.setdefault("ADAAD_CONTAINER_HASH", "sha256:container-fixed")


def main() -> int:
    _set_deterministic_env()
    with tempfile.TemporaryDirectory(prefix="evidence-determinism-") as temp_dir:
        root = Path(temp_dir)
        first = _build_bundle(root / "run_a")
        second = _build_bundle(root / "run_b")
        normalized_first = dict(first)
        normalized_second = dict(second)
        normalized_first["export_metadata"] = dict(first["export_metadata"])
        normalized_second["export_metadata"] = dict(second["export_metadata"])
        normalized_first["export_metadata"].pop("path", None)
        normalized_second["export_metadata"].pop("path", None)

    checks = {
        "bundle_digest": first["export_metadata"]["digest"] == second["export_metadata"]["digest"],
        "signature": first["export_metadata"]["signer"]["signature"] == second["export_metadata"]["signer"]["signature"],
        "lineage": first["lineage_anchors"] == second["lineage_anchors"],
        "canonical_bundle": canonical_json(normalized_first) == canonical_json(normalized_second),
    }
    if not all(checks.values()):
        print("evidence_subsystem_determinism:FAILED")
        print(json.dumps(checks, sort_keys=True, indent=2))
        return 1

    digest = hashlib.sha256(canonical_json(normalized_first).encode("utf-8")).hexdigest()
    print(f"evidence_subsystem_determinism:PASSED:digest={digest[:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
