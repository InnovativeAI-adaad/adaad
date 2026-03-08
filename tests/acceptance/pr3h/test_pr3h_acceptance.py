# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from app.main import Orchestrator
from runtime.evolution.checkpoint_registry import CheckpointRegistry
from runtime.evolution.lineage_v2 import LineageLedgerV2
from runtime.evolution.runtime import EvolutionRuntime

FIXTURE_PATH = Path(__file__).with_name("fixtures") / "entropy_triage_replay_cases.json"
pytestmark = pytest.mark.pr3h_acceptance


class _WarmPoolStub:
    def start(self) -> None:
        return


class _RuntimeStub:
    def __init__(self, ledger: LineageLedgerV2) -> None:
        self.ledger = ledger


@pytest.mark.pr3h_checkpoint_tamper
def test_pr3h_checkpoint_tamper_escalates_and_fail_closes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ledger = LineageLedgerV2(tmp_path / "lineage_v2.jsonl")
    epoch_id = "epoch-pr3h-tamper"
    ledger.append_event("MutationBundleEvent", {"epoch_id": epoch_id, "epoch_digest": "sha256:abc"})
    CheckpointRegistry(ledger).create_checkpoint(epoch_id)

    ledger.append_event(
        "EpochCheckpointEvent",
        {
            "epoch_id": epoch_id,
            "checkpoint_id": "chk_tampered",
            "checkpoint_hash": "sha256:" + ("0" * 64),
            "prev_checkpoint_hash": "sha256:" + ("f" * 64),
            "epoch_digest": "sha256:abc",
            "baseline_digest": "sha256:abc",
            "mutation_count": 1,
            "promotion_event_count": 0,
            "scoring_event_count": 0,
            "entropy_policy_hash": "sha256:" + ("0" * 64),
            "promotion_policy_hash": "sha256:" + ("0" * 64),
            "evidence_hash": "sha256:" + ("0" * 64),
            "sandbox_policy_hash": "sha256:" + ("0" * 64),
        },
    )

    monkeypatch.setattr("app.main.verify_all", lambda: (True, []))

    orchestrator = object.__new__(Orchestrator)
    orchestrator.state = {"status": "initializing", "mutation_enabled": False}
    orchestrator.warm_pool = _WarmPoolStub()
    orchestrator.evolution_runtime = _RuntimeStub(ledger)

    def _fail(reason: str) -> None:
        raise RuntimeError(reason)

    orchestrator._fail = _fail

    journal_actions: list[str] = []

    def _write_entry(*, agent_id: str, action: str, payload: dict) -> None:
        journal_actions.append(action)

    monkeypatch.setattr("app.main.journal.write_entry", _write_entry)

    with pytest.raises(RuntimeError, match=r"^checkpoint_chain_violated:checkpoint_prev_missing:epoch=epoch-pr3h-tamper;index=1$"):
        orchestrator._verify_checkpoint_chain()

    assert orchestrator.state["mutation_enabled"] is False
    assert journal_actions == ["checkpoint_chain_violated"]


@pytest.mark.pr3h_entropy_triage
def test_pr3h_entropy_triage_replay_fixtures_fail_closed() -> None:
    fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    runtime = EvolutionRuntime()
    runtime.ledger.list_epoch_ids = mock.Mock(return_value=["epoch-fixture"])  # type: ignore[method-assign]
    runtime.governor.enter_fail_closed = mock.Mock()  # type: ignore[method-assign]

    for fixture in fixtures:
        runtime.verify_epoch = mock.Mock(  # type: ignore[method-assign]
            return_value={
                "epoch_id": "epoch-fixture",
                "baseline_epoch": "epoch-fixture",
                "baseline_source": "lineage_epoch_digest",
                "expected_digest": fixture["expected_digest"],
                "actual_digest": fixture["actual_digest"],
                "passed": False,
                "decision": "diverge",
                "replay_score": fixture["replay_score"],
                "cause_buckets": fixture["cause_buckets"],
            }
        )

        result = runtime.replay_preflight("strict")

        assert result["has_divergence"] is True, fixture["case_id"]
        assert result["decision"] == fixture["expected_decision"], fixture["case_id"]
        detail = result["results"][0]
        assert detail["cause_buckets"] == fixture["cause_buckets"], fixture["case_id"]
        assert detail["replay_score"] == fixture["replay_score"], fixture["case_id"]

    assert runtime.governor.enter_fail_closed.call_count == len(fixtures)
