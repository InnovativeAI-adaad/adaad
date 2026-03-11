# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import pytest
pytestmark = pytest.mark.governance_gate

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

from runtime.constitution import POLICY_HASH
from runtime.governance.amendment import AmendmentEngine
from runtime.governance.foundation import SeededDeterminismProvider
from runtime.tools.execution_contract import ToolExecutionRequest


def test_amendment_lifecycle_propose_approve_reject(tmp_path: Path, monkeypatch) -> None:
    from runtime.governance import amendment

    writes = []
    txs = []
    review_events = []
    monkeypatch.setattr(amendment.journal, "write_entry", lambda **kwargs: writes.append(kwargs))

    def _append_tx(tx_type, payload, tx_id=None):
        tx_hash = hashlib.sha256(f"{tx_type}:{payload}".encode("utf-8")).hexdigest()
        entry = {"tx": tx_id or "tx", "type": tx_type, "payload": payload, "prev_hash": "0" * 64, "hash": tx_hash}
        txs.append(entry)
        return entry

    monkeypatch.setattr(amendment.journal, "append_tx", _append_tx)
    monkeypatch.setattr(amendment, "record_review_quality", lambda payload: review_events.append(payload))

    policy = Path("runtime/governance/constitution.yaml").read_text(encoding="utf-8")
    policy = policy.replace('"SANDBOX": "advisory"', '"SANDBOX": "warning"', 1)
    expected_hash = hashlib.sha256(policy.encode("utf-8")).hexdigest()
    monkeypatch.setattr(amendment, "reload_constitution_policy", lambda: expected_hash)

    engine = AmendmentEngine(proposals_dir=tmp_path / "proposals", required_approvals=2)
    proposal = engine.propose_amendment(
        proposer="alice",
        new_policy_text=policy,
        rationale="test rationale",
        old_policy_hash=POLICY_HASH,
    )
    assert proposal.status == "pending"

    proposal = engine.approve_amendment(proposal.proposal_id, "bob", comment_count=2)
    assert proposal.status == "pending"

    proposal = engine.approve_amendment(proposal.proposal_id, "carol", comment_count=1)
    assert proposal.status == "approved"

    proposal = engine.reject_amendment(proposal.proposal_id, "dave", comment_count=3, overridden=True)
    assert proposal.status == "rejected"

    phases = [item["payload"]["phase"] for item in txs if item["type"] == "constitutional_amendment_phase"]
    assert "simulation_gate" in phases
    assert "quorum_vote" in phases
    assert "effectuation" in phases
    assert writes
    assert len(review_events) == 3
    assert review_events[0]["decision"] == "approve"
    assert review_events[-1]["decision"] == "reject"
    assert review_events[-1]["overridden"] is True


def test_review_latency_uses_injected_provider_clock(tmp_path: Path, monkeypatch) -> None:
    from runtime.governance import amendment

    review_events = []
    monkeypatch.setattr(amendment.journal, "write_entry", lambda **kwargs: None)
    monkeypatch.setattr(
        amendment.journal,
        "append_tx",
        lambda tx_type, payload, tx_id=None: {"tx": tx_id or "tx", "type": tx_type, "payload": payload},
    )
    monkeypatch.setattr(amendment, "record_review_quality", lambda payload: review_events.append(payload))
    monkeypatch.setattr(amendment, "reload_constitution_policy", lambda **kwargs: hashlib.sha256(b'{"SANDBOX":"warning"}').hexdigest())

    provider = SeededDeterminismProvider(seed="latency", fixed_now=datetime(2027, 1, 1, 0, 1, 30, tzinfo=timezone.utc))
    engine = AmendmentEngine(proposals_dir=tmp_path / "proposals", required_approvals=1, provider=provider)
    proposal = engine.propose_amendment(
        proposer="alice",
        new_policy_text='{"SANDBOX":"warning"}',
        rationale="clock-injection",
        old_policy_hash=POLICY_HASH,
    )
    proposal.timestamp = "2027-01-01T00:00:00Z"
    engine._save_proposal(proposal)
    engine.approve_amendment(proposal.proposal_id, "bob")

    assert review_events
    assert review_events[-1]["latency_seconds"] == 90.0


def test_review_quality_payload_stable_under_replay(tmp_path: Path, monkeypatch) -> None:
    from runtime.governance import amendment

    payloads = []
    monkeypatch.setattr(amendment.journal, "write_entry", lambda **kwargs: None)
    monkeypatch.setattr(
        amendment.journal,
        "append_tx",
        lambda tx_type, payload, tx_id=None: {"tx": tx_id or "tx", "type": tx_type, "payload": payload},
    )
    monkeypatch.setattr(amendment, "record_review_quality", lambda payload: payloads.append(payload))
    monkeypatch.setattr(amendment, "reload_constitution_policy", lambda: hashlib.sha256('{"SANDBOX":"warning"}'.encode("utf-8")).hexdigest())

    provider = SeededDeterminismProvider(seed="replay", fixed_now=datetime(2028, 2, 2, 8, 0, 0, tzinfo=timezone.utc))
    engine = AmendmentEngine(
        proposals_dir=tmp_path / "proposals",
        required_approvals=1,
        provider=provider,
        replay_mode="strict",
    )
    proposal = engine.propose_amendment(
        proposer="alice",
        new_policy_text='{"SANDBOX":"warning"}',
        rationale="replay-stability",
        old_policy_hash=POLICY_HASH,
    )
    engine.approve_amendment(proposal.proposal_id, "bob", comment_count=3, overridden=False)
    first_payload = dict(payloads[-1])

    payloads.clear()
    engine.approve_amendment(proposal.proposal_id, "bob", comment_count=3, overridden=False)
    second_payload = dict(payloads[-1])

    assert first_payload == second_payload


def test_effectuation_idempotent_noop(tmp_path: Path, monkeypatch) -> None:
    from runtime.governance import amendment

    writes = []
    txs = []
    monkeypatch.setattr(amendment.journal, "write_entry", lambda **kwargs: writes.append(kwargs))

    def _append_tx(tx_type, payload, tx_id=None):
        prev = txs[-1]["hash"] if txs else "0" * 64
        tx_hash = hashlib.sha256(f"{prev}:{payload}".encode("utf-8")).hexdigest()
        entry = {"tx": tx_id or "tx", "type": tx_type, "payload": payload, "prev_hash": prev, "hash": tx_hash}
        txs.append(entry)
        return entry

    monkeypatch.setattr(amendment.journal, "append_tx", _append_tx)
    monkeypatch.setattr(amendment, "record_review_quality", lambda payload: None)

    policy = Path("runtime/governance/constitution.yaml").read_text(encoding="utf-8")
    expected_hash = hashlib.sha256(policy.encode("utf-8")).hexdigest()

    engine = AmendmentEngine(proposals_dir=tmp_path / "proposals", required_approvals=1)
    proposal = engine.propose_amendment(
        proposer="alice",
        new_policy_text=policy,
        rationale="already effective",
        old_policy_hash=POLICY_HASH,
    )
    proposal.new_policy_hash = expected_hash
    engine._save_proposal(proposal)

    proposal = engine.approve_amendment(proposal.proposal_id, "bob")
    assert proposal.status == "approved"
    assert any(w["action"] == "constitutional_amendment_already_effective" for w in writes)

    phase_entries = [item for item in txs if item["type"] == "constitutional_amendment_phase"]
    effectuation = [item for item in phase_entries if item["payload"]["phase"] == "effectuation"]
    assert effectuation
    assert effectuation[-1]["payload"]["state"] == "amendment_already_effective"
    assert effectuation[-1]["payload"]["proposal_id"] == proposal.proposal_id


def test_simulation_gate_blocks_on_tool_contract_failure(tmp_path: Path, monkeypatch) -> None:
    from runtime.governance import amendment

    monkeypatch.setattr(amendment.journal, "write_entry", lambda **kwargs: None)
    monkeypatch.setattr(
        amendment.journal,
        "append_tx",
        lambda tx_type, payload, tx_id=None: {"tx": tx_id or "tx", "type": tx_type, "payload": payload},
    )
    monkeypatch.setattr(amendment, "record_review_quality", lambda payload: None)

    policy = Path("runtime/governance/constitution.yaml").read_text(encoding="utf-8")
    failing_request = ToolExecutionRequest(
        tool_id="lint-failure",
        check_kind="lint",
        command=(sys.executable, "-c", "import sys; sys.exit(1)"),
    )
    engine = AmendmentEngine(
        proposals_dir=tmp_path / "proposals",
        required_approvals=1,
        simulation_tool_requests=(failing_request,),
    )
    proposal = engine.propose_amendment(
        proposer="alice",
        new_policy_text=policy,
        rationale="tool-contract-gate",
        old_policy_hash=POLICY_HASH,
    )

    proposal = engine.approve_amendment(proposal.proposal_id, "bob")
    assert proposal.status == "pending"

    loaded = engine._load_proposal(proposal.proposal_id)
    simulation_entries = [entry for entry in loaded.phase_transitions if entry["phase"] == "simulation_gate"]
    assert simulation_entries
    assert simulation_entries[-1]["state"] == "failed"
