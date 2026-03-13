# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import pytest
pytestmark = pytest.mark.governance_gate

from runtime.governance.foundation.hashing import ZERO_HASH
from runtime.governance.pr_lifecycle_event_contract import build_event_digest
from runtime.governance.validators.promotion_contract import PromotionContractViolation, validate_promotion_policy_event


def _event(decision_id: str = "d-1", *, schema_version: str = "1.0") -> dict[str, object]:
    event = {
        "schema_version": schema_version,
        "event_id": "prl_abc123",
        "event_type": "promotion_policy_evaluated",
        "pr_number": 1,
        "commit_sha": "a" * 40,
        "idempotency_key": "sha256:" + "b" * 64,
        "attempt": 1,
        "sequence": 1,
        "emitted_at": "2026-01-01T00:00:00Z",
        "correlation_id": "promotion:d-1",
        "previous_event_digest": ZERO_HASH,
        "event_digest": "",
        "payload": {
            "policy_version": "promotion-policy.v1",
            "evaluation_result": "allow",
            "decision_id": decision_id,
        },
    }
    if schema_version == "1.1":
        event["synthetic_commit_id"] = "sha256:" + ("c" * 64)
    event["event_digest"] = build_event_digest(event)
    return event


def test_rejects_duplicate_decision_id() -> None:
    event = _event("dup-id")
    lineage_entries = [{"type": "PRLifecycleEvent", "payload": _event("dup-id")}]

    try:
        validate_promotion_policy_event(event=event, lineage_entries=lineage_entries)
        raise AssertionError("expected duplicate decision_id violation")
    except PromotionContractViolation as exc:
        assert str(exc) == "duplicate:decision_id"


def test_accepts_valid_schema_event() -> None:
    event = _event("fresh-id")
    validate_promotion_policy_event(event=event, lineage_entries=[])


def test_accepts_v11_schema_event_with_synthetic_commit_id() -> None:
    event = _event("fresh-v11", schema_version="1.1")
    validate_promotion_policy_event(event=event, lineage_entries=[])


def test_v11_schema_rejects_missing_synthetic_commit_id() -> None:
    event = _event("missing-v11", schema_version="1.1")
    event.pop("synthetic_commit_id", None)
    event["event_digest"] = build_event_digest(event)

    with pytest.raises(PromotionContractViolation, match="invalid:synthetic_commit_id"):
        validate_promotion_policy_event(event=event, lineage_entries=[])
