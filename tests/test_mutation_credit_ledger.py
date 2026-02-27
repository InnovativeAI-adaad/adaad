# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

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
