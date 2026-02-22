# SPDX-License-Identifier: Apache-2.0

import json

from app.agents.mutation_request import MutationRequest
from runtime.constitution import VALIDATOR_REGISTRY, deterministic_envelope_scope
from security.ledger import journal


def _write_ledger_entries(path, action: str, count: int, *, epoch_id: str) -> None:
    now_iso = "2026-01-01T00:00:00Z"
    lines = []
    for _ in range(count):
        lines.append(
            json.dumps(
                {
                    "timestamp": now_iso,
                    "agent_id": "test_subject",
                    "action": action,
                    "payload": {"epoch_id": epoch_id},
                },
                sort_keys=True,
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_mutation_rate_rejects_when_window_threshold_exceeded(monkeypatch, tmp_path) -> None:
    ledger_path = tmp_path / "lineage.jsonl"
    monkeypatch.setattr(journal, "LEDGER_FILE", ledger_path)
    _write_ledger_entries(ledger_path, "mutation_executed", count=3, epoch_id="epoch-1")

    monkeypatch.setenv("ADAAD_MAX_MUTATION_RATE", "2")
    monkeypatch.setenv("ADAAD_MUTATION_RATE_WINDOW_SEC", "3600")

    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="now",
        intent="test",
        ops=[],
        signature="sig",
        nonce="nonce",
        epoch_id="epoch-1",
    )

    validator = VALIDATOR_REGISTRY["max_mutation_rate"]
    with deterministic_envelope_scope({"tier": "PRODUCTION", "agent_id": "test_subject", "epoch_id": "epoch-1"}):
        result = validator(request)

    assert result["ok"] is False
    assert result["reason"] == "rate_limit_exceeded"
    assert result["details"]["rate_per_hour"] == 3.0
