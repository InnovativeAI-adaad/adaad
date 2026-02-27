# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

from adaad.agents.mutation_request import MutationRequest
from app.main import Orchestrator
from runtime import metrics
from runtime import constitution


def _read_metrics_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    return events


def test_entropy_budget_constitutional_rejection_preserves_state_and_chain(monkeypatch, tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.jsonl"
    ledger_path = tmp_path / "lineage_v2.jsonl"

    monkeypatch.setattr(metrics, "METRICS_PATH", metrics_path)
    monkeypatch.setattr("runtime.evolution.lineage_v2.LEDGER_V2_PATH", ledger_path)
    monkeypatch.setenv("ADAAD_FORCE_DETERMINISTIC_PROVIDER", "1")
    monkeypatch.setenv("ADAAD_DETERMINISTIC_SEED", "entropy-integration-seed")
    monkeypatch.setenv("ADAAD_FORCE_TIER", "PRODUCTION")
    monkeypatch.setenv("ADAAD_MAX_MUTATION_ENTROPY_BITS", "1")
    monkeypatch.setenv("ADAAD_MAX_EPOCH_ENTROPY_BITS", "4096")
    monkeypatch.setitem(constitution.VALIDATOR_REGISTRY, "signature_required", lambda _request: {"ok": True, "reason": "signature_ok", "details": {}})
    monkeypatch.setitem(constitution.VALIDATOR_REGISTRY, "lineage_continuity", lambda _request: {"ok": True, "reason": "lineage_ok", "details": {}})

    dna_path = Path("app/agents/test_subject/dna.json")
    before_dna = dna_path.read_text(encoding="utf-8")

    orchestrator = Orchestrator(dry_run=False)
    request = MutationRequest(
        agent_id="test_subject",
        generation_ts="now",
        intent="entropy-integration",
        ops=[{"op": "set", "path": "/traits/entropy_integration", "value": "blocked"}],
        signature="cryovant-dev-seed",
        nonce="entropy-integration-nonce",
    )
    monkeypatch.setattr(orchestrator.architect, "propose_mutations", lambda: [request])
    monkeypatch.setattr(orchestrator.mutation_engine, "select", lambda proposals: (request, {"entropy-integration": 1.0}))

    orchestrator._run_mutation_cycle()

    after_dna = dna_path.read_text(encoding="utf-8")
    assert after_dna == before_dna

    events = _read_metrics_events(metrics_path)
    entropy_rejections = [event for event in events if event.get("event") == "mutation_rejected_entropy"]
    assert entropy_rejections, "expected mutation_rejected_entropy event"

    rejection_payload = entropy_rejections[-1]["payload"]
    constitutional_verdict = rejection_payload["constitutional_verdict"]
    entropy_verdict = next(item for item in constitutional_verdict["verdicts"] if item["rule"] == "entropy_budget_limit")

    assert constitutional_verdict["passed"] is False
    assert "entropy_budget_limit" in constitutional_verdict["blocking_failures"]
    entropy_details = entropy_verdict["details"]["details"]
    assert entropy_details["max_mutation_entropy_bits"] == 1
    assert "epoch_entropy_bits" in entropy_details

    orchestrator.evolution_runtime.ledger.verify_integrity()
    entries = orchestrator.evolution_runtime.ledger.read_all()
    assert entries, "expected lineage entries for integrity assertions"
    for idx in range(1, len(entries)):
        assert entries[idx]["prev_hash"] == entries[idx - 1]["hash"]
