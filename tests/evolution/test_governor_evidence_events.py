# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from runtime.evolution.governor import EvolutionGovernor
from runtime.evolution.lineage_v2 import LineageLedgerV2
from runtime.governance.foundation import SeededDeterminismProvider
from runtime.api.agents import MutationRequest


class _Impact:
    def __init__(self, total: float) -> None:
        self.total = total


def _request(*, intent: str, authority_level: str = "high-impact") -> MutationRequest:
    return MutationRequest(
        agent_id="agent-evidence",
        generation_ts="2026-03-19T00:00:00Z",
        intent=intent,
        ops=[{"op": "replace", "path": "runtime/foo.py", "value": "x=1"}],
        signature="cryovant-dev-test",
        nonce="nonce-001",
        epoch_id="epoch-evidence",
        authority_level=authority_level,
        capability_scopes=["mutation"],
    )


def test_governor_emits_mutation_evidence_event_on_accept(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADAAD_ENV", "dev")
    monkeypatch.setenv("CRYOVANT_DEV_MODE", "1")
    ledger = LineageLedgerV2(tmp_path / "lineage_governor_evidence_accept.jsonl")
    governor = EvolutionGovernor(ledger=ledger, provider=SeededDeterminismProvider("seed-evidence"))
    governor.mark_epoch_start("epoch-evidence")
    governor.impact_scorer.score = lambda _request: _Impact(total=0.1)  # type: ignore[method-assign]

    decision = governor.validate_bundle(_request(intent="governance_mutation"), epoch_id="epoch-evidence")
    assert decision.accepted is True
    events = [entry for entry in ledger.read_epoch("epoch-evidence") if entry.get("type") == "MutationEvidenceEvent"]
    assert events
    payload = events[-1]["payload"]
    assert payload["evidence_scope_required"] is True
    assert payload["evidence_bundle_present"] is True
    assert payload["evidence_bundle_valid"] is True


def test_governor_emits_mutation_evidence_event_on_reject(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ADAAD_ENV", "dev")
    monkeypatch.setenv("CRYOVANT_DEV_MODE", "1")
    ledger = LineageLedgerV2(tmp_path / "lineage_governor_evidence_reject.jsonl")
    governor = EvolutionGovernor(ledger=ledger, provider=SeededDeterminismProvider("seed-evidence-reject"))
    governor.mark_epoch_start("epoch-evidence")
    governor.impact_scorer.score = lambda _request: _Impact(total=1.5)  # type: ignore[method-assign]

    decision = governor.validate_bundle(_request(intent="governance_mutation"), epoch_id="epoch-evidence")
    assert decision.accepted is False
    events = [entry for entry in ledger.read_epoch("epoch-evidence") if entry.get("type") == "MutationEvidenceEvent"]
    assert events
    payload = events[-1]["payload"]
    assert payload["evidence_scope_required"] is True
    assert payload["evidence_bundle_present"] is False
