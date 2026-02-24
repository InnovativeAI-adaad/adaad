# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
from pathlib import Path

from runtime.constitution import POLICY_HASH
from runtime.governance.amendment import AmendmentEngine


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
