# SPDX-License-Identifier: Apache-2.0
"""Promotion lifecycle contract validation before lineage append."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from runtime.governance.pr_lifecycle_event_contract import build_event_digest

_SHA256_RE = re.compile(r"^sha256:[a-f0-9]{64}$")
_COMMIT_SHA_RE = re.compile(r"^[a-f0-9]{40}$")


class PromotionContractViolation(ValueError):
    """Raised when a promotion lifecycle event violates governance contract."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PromotionContractViolation(code)


def validate_promotion_policy_event(*, event: Mapping[str, Any], lineage_entries: Sequence[Mapping[str, Any]]) -> None:
    """Enforce schema conformance + decision_id uniqueness across lineage history."""

    required_fields = (
        "schema_version",
        "event_id",
        "event_type",
        "pr_number",
        "commit_sha",
        "idempotency_key",
        "attempt",
        "sequence",
        "emitted_at",
        "correlation_id",
        "previous_event_digest",
        "event_digest",
        "payload",
    )
    for field in required_fields:
        _require(field in event, f"missing:{field}")

    _require(event["schema_version"] == "1.0", "schema_version_mismatch")
    _require(event["event_type"] == "promotion_policy_evaluated", "event_type_mismatch")
    _require(isinstance(event["event_id"], str) and bool(event["event_id"].strip()), "invalid:event_id")
    _require(isinstance(event["pr_number"], int) and event["pr_number"] >= 1, "invalid:pr_number")
    _require(isinstance(event["attempt"], int) and event["attempt"] >= 1, "invalid:attempt")
    _require(isinstance(event["sequence"], int) and event["sequence"] >= 1, "invalid:sequence")
    _require(isinstance(event["commit_sha"], str) and bool(_COMMIT_SHA_RE.fullmatch(event["commit_sha"])), "invalid:commit_sha")
    _require(isinstance(event["idempotency_key"], str) and bool(_SHA256_RE.fullmatch(event["idempotency_key"])), "invalid:idempotency_key")
    _require(isinstance(event["previous_event_digest"], str) and bool(_SHA256_RE.fullmatch(event["previous_event_digest"])), "invalid:previous_event_digest")
    _require(isinstance(event["event_digest"], str) and bool(_SHA256_RE.fullmatch(event["event_digest"])), "invalid:event_digest")

    payload = event["payload"]
    _require(isinstance(payload, dict), "invalid:payload")
    _require(set(payload.keys()) == {"policy_version", "evaluation_result", "decision_id"}, "invalid:payload_shape")
    _require(isinstance(payload.get("policy_version"), str) and bool(str(payload.get("policy_version", "")).strip()), "invalid:policy_version")
    _require(payload.get("evaluation_result") in {"allow", "deny"}, "invalid:evaluation_result")
    _require(isinstance(payload.get("decision_id"), str) and bool(str(payload.get("decision_id", "")).strip()), "invalid:decision_id")

    expected_digest = build_event_digest(event)
    _require(event["event_digest"] == expected_digest, "event_digest_mismatch")

    decision_id = str(payload["decision_id"])
    for entry in lineage_entries:
        entry_payload = entry.get("payload") if isinstance(entry, Mapping) else None
        if not isinstance(entry_payload, Mapping):
            continue
        if entry_payload.get("event_type") != "promotion_policy_evaluated":
            continue
        nested_payload = entry_payload.get("payload")
        if isinstance(nested_payload, Mapping) and str(nested_payload.get("decision_id") or "") == decision_id:
            raise PromotionContractViolation("duplicate:decision_id")


__all__ = ["PromotionContractViolation", "validate_promotion_policy_event"]
