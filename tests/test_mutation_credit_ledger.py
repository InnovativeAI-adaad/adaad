# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.evolution.mutation_credit_ledger import (
    ZERO_HASH,
    MutationCreditEvent,
    MutationCreditLedger,
    MutationCreditLedgerError,
)


def test_append_only_hash_chain_and_replay_balances(tmp_path: Path) -> None:
    ledger = MutationCreditLedger(tmp_path / "mutation_credit_ledger.jsonl")

    first = ledger.append(
        MutationCreditEvent(
            agent_id="agent-alpha",
            mutation_id="m-1",
            credits_delta=10,
            budget_source="EARNED",
            idempotency_key="evt-1",
            details={"source": "market", "tags": ["prod"]},
        )
    )
    second = ledger.append(
        MutationCreditEvent(
            agent_id="agent-alpha",
            mutation_id="m-2",
            credits_delta=-3,
            budget_source="EARNED",
            idempotency_key="evt-2",
            details={"source": "rollback"},
        )
    )

    assert first["prev_hash"] == ZERO_HASH
    assert second["prev_hash"] == first["record_hash"]
    assert ledger.verify_integrity()["ok"] is True
    assert ledger.replay_balances() == {"agent-alpha": 7}


def test_idempotency_is_stable_and_conflicts_fail_closed(tmp_path: Path) -> None:
    ledger = MutationCreditLedger(tmp_path / "mutation_credit_ledger.jsonl")
    event = MutationCreditEvent(
        agent_id="agent-alpha",
        mutation_id="m-1",
        credits_delta=5,
        budget_source="EARNED",
        idempotency_key="evt-1",
        details={"nested": {"b": 2, "a": 1}},
    )

    first = ledger.append(event)
    second = ledger.append(event)
    assert second == first

    with pytest.raises(MutationCreditLedgerError, match="idempotency_key_conflict"):
        ledger.append(
            MutationCreditEvent(
                agent_id="agent-alpha",
                mutation_id="m-2",
                credits_delta=6,
                budget_source="EARNED",
                idempotency_key="evt-1",
                details={"nested": {"a": 1, "b": 2}},
            )
        )


def test_verify_integrity_detects_tamper(tmp_path: Path) -> None:
    path = tmp_path / "mutation_credit_ledger.jsonl"
    ledger = MutationCreditLedger(path)
    ledger.append(
        MutationCreditEvent(
            agent_id="agent-alpha",
            mutation_id="m-1",
            credits_delta=2,
            budget_source="EARNED",
            idempotency_key="evt-1",
        )
    )

    row = json.loads(path.read_text(encoding="utf-8").strip())
    row["event"]["credits_delta"] = 999
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    result = ledger.verify_integrity()
    assert result["ok"] is False
    assert result["reason"] == "record_hash_mismatch"

    with pytest.raises(MutationCreditLedgerError, match="integrity_failure"):
        ledger.replay_balances()


def test_idempotency_index_rebuild_when_missing(tmp_path: Path) -> None:
    ledger_path = tmp_path / "mutation_credit_ledger.jsonl"
    ledger = MutationCreditLedger(ledger_path)
    first = MutationCreditEvent(
        agent_id="agent-alpha",
        mutation_id="m-1",
        credits_delta=4,
        budget_source="EARNED",
        idempotency_key="evt-idx-1",
    )
    second = MutationCreditEvent(
        agent_id="agent-alpha",
        mutation_id="m-2",
        credits_delta=6,
        budget_source="EARNED",
        idempotency_key="evt-idx-2",
    )
    ledger.append(first)
    ledger.append(second)

    ledger_path.with_suffix(".jsonl.idempotency.jsonl").unlink()
    replay = ledger.append(second)

    assert replay["event"]["idempotency_key"] == "evt-idx-2"
    assert len(tuple(ledger.events())) == 2


def test_integrity_detects_sidecar_mismatch_and_recovers(tmp_path: Path) -> None:
    ledger_path = tmp_path / "mutation_credit_ledger.jsonl"
    ledger = MutationCreditLedger(ledger_path)
    ledger.append(
        MutationCreditEvent(
            agent_id="agent-alpha",
            mutation_id="m-1",
            credits_delta=4,
            budget_source="EARNED",
            idempotency_key="evt-1",
        )
    )
    ledger.append(
        MutationCreditEvent(
            agent_id="agent-alpha",
            mutation_id="m-2",
            credits_delta=5,
            budget_source="EARNED",
            idempotency_key="evt-2",
        )
    )

    sidecar = ledger_path.with_suffix(".jsonl.tail.json")
    sidecar.write_text('{"record_hash":"sha256:bad","entries":999}\n', encoding="utf-8")

    third = ledger.append(
        MutationCreditEvent(
            agent_id="agent-alpha",
            mutation_id="m-3",
            credits_delta=1,
            budget_source="EARNED",
            idempotency_key="evt-3",
        )
    )

    assert third["prev_hash"].startswith("sha256:")
    assert ledger.verify_integrity()["ok"] is True
