# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest
pytestmark = pytest.mark.governance_gate

from runtime.governance.canon_law import CanonLawError, load_canon_law, one_way_escalation, violation_event_payload
from runtime.governance.gate_certifier import GateCertifier
from runtime.governance.policy_lifecycle import PolicyLifecycleError, apply_transition
from runtime.governance.policy_validator import PolicyValidator


def _proof(*, digest: str, prev: str = "sha256:" + "0" * 64) -> dict:
    return {
        "artifact_digest": digest,
        "previous_transition_hash": prev,
        "evidence": {"approver": "operator-1", "ticket": "GOV-1"},
    }


def test_deterministic_replay_violation_payload_hash() -> None:
    clause = load_canon_law()["IV.gate_forbidden_code_block"]
    first = violation_event_payload(component="gate_certifier", clause=clause, reason="forbidden_code_or_import", context={"path": "x.py"})
    second = violation_event_payload(component="gate_certifier", clause=clause, reason="forbidden_code_or_import", context={"path": "x.py"})
    assert first == second
    assert first["payload_hash"].startswith("sha256:")


def test_escalation_tier_per_article_breach(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("runtime.governance.canon_law.append_tx", lambda **kwargs: {"hash": "h", **kwargs})

    validator = PolicyValidator().validate("")
    assert validator.escalation == "conservative"

    target = tmp_path / "bad_import.py"
    target.write_text("import subprocess\n", encoding="utf-8")
    monkeypatch.setattr("security.cryovant.verify_governance_token", lambda token: True)
    cert = GateCertifier().certify(target, {"cryovant_token": "token"})
    assert cert["escalation"] == "governance"

    digest = "sha256:" + "1" * 64
    with pytest.raises(PolicyLifecycleError, match="escalation=critical"):
        apply_transition(
            artifact_digest=digest,
            from_state="review-approved",
            to_state="signed",
            proof=_proof(digest="sha256:" + "2" * 64),
        )


def test_mutation_blocking_for_governance_and_critical_tiers(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("runtime.governance.canon_law.append_tx", lambda **kwargs: {"hash": "h", **kwargs})
    target = tmp_path / "bad.py"
    target.write_text("import subprocess\n", encoding="utf-8")
    monkeypatch.setattr("security.cryovant.verify_governance_token", lambda token: True)

    cert = GateCertifier().certify(target, {"cryovant_token": "token"})
    assert cert["mutation_blocked"] is True

    digest = "sha256:" + "3" * 64
    with pytest.raises(PolicyLifecycleError, match="mutation_blocked=True"):
        apply_transition(
            artifact_digest=digest,
            from_state="review-approved",
            to_state="signed",
            proof=_proof(digest="sha256:" + "4" * 64),
        )


def test_ledger_event_emission_hash_stable_payload_structure(tmp_path: Path, monkeypatch) -> None:
    events = []

    def _append_tx(*, tx_type, payload, tx_id=None):
        events.append({"tx_type": tx_type, "payload": payload, "tx_id": tx_id})
        return {"hash": f"hash-{len(events)}"}

    monkeypatch.setattr("runtime.governance.canon_law.append_tx", _append_tx)
    target = tmp_path / "bad.py"
    target.write_text("import subprocess\n", encoding="utf-8")
    monkeypatch.setattr("security.cryovant.verify_governance_token", lambda token: True)
    GateCertifier().certify(target, {"cryovant_token": "token"})

    assert events
    payload = events[0]["payload"]
    assert set(payload) == {
        "component",
        "article",
        "clause_id",
        "reason",
        "escalation",
        "mutation_block",
        "fail_closed",
        "context",
        "payload_hash",
    }
    cloned = dict(payload)
    assert payload["payload_hash"] == cloned["payload_hash"]


def test_one_way_escalation_no_auto_deescalation_and_fail_closed_undefined() -> None:
    assert one_way_escalation("governance", "advisory") == "governance"
    with pytest.raises(CanonLawError):
        one_way_escalation("governance", "unknown")
