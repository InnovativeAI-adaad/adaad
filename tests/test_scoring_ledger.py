# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from runtime.evolution.agm_event import DeploymentGatingEvent, ScoringEvent
from runtime.evolution.scoring_ledger import ScoringLedger


def test_scoring_ledger_hash_chain(tmp_path: Path) -> None:
    ledger = ScoringLedger(tmp_path / "scoring.jsonl")
    first = ledger.append(ScoringEvent(mutation_id="m1", score=1.0))
    second = ledger.append(ScoringEvent(mutation_id="m2", score=2.0))

    assert first["prev_hash"] == "sha256:" + ("0" * 64)
    assert second["prev_hash"] == first["record_hash"]
    assert ledger.last_hash() == second["record_hash"]


def test_scoring_ledger_enforces_step_11_contract_for_deployment_gating(tmp_path: Path) -> None:
    ledger = ScoringLedger(tmp_path / "scoring.jsonl")
    record = ledger.append(
        DeploymentGatingEvent(
            environment="prod",
            gate_decision="allow",
            step_11_commit_sha="a" * 40,
            step_11_contract_passed=True,
        )
    )

    assert record["event"]["event_type"] == "deployment_gating_event"
