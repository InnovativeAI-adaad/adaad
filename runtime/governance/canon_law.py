# SPDX-License-Identifier: Apache-2.0
"""Canonical governance law artifact loading and deterministic enforcement helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import json

from runtime.governance.foundation import canonical_json, sha256_prefixed_digest
from security.ledger.journal import append_tx

CANON_LAW_PATH = Path("runtime/governance/canon_law_v1.yaml")
ESCALATION_ORDER: dict[str, int] = {
    "advisory": 1,
    "conservative": 2,
    "governance": 3,
    "critical": 4,
}


@dataclass(frozen=True)
class CanonClause:
    article: str
    clause_id: str
    applies_to: str
    enforcement: str
    escalation: str
    mutation_block: bool
    fail_closed: bool


class CanonLawError(RuntimeError):
    """Raised when canonical law artifact cannot be interpreted safely."""


def _validate_escalation(value: Any) -> str:
    if not isinstance(value, str) or value not in ESCALATION_ORDER:
        raise CanonLawError(f"undefined escalation state: {value!r}")
    return value


def load_canon_law(path: Path = CANON_LAW_PATH) -> dict[str, CanonClause]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    clauses_raw = raw.get("clauses") if isinstance(raw, dict) else None
    if not isinstance(clauses_raw, list) or not clauses_raw:
        raise CanonLawError("canon law artifact missing clauses")
    clauses: dict[str, CanonClause] = {}
    for item in clauses_raw:
        if not isinstance(item, dict):
            raise CanonLawError("canon law clause must be object")
        escalation = _validate_escalation(item.get("escalation"))
        clause = CanonClause(
            article=str(item.get("article") or ""),
            clause_id=str(item.get("clause_id") or ""),
            applies_to=str(item.get("applies_to") or ""),
            enforcement=str(item.get("enforcement") or ""),
            escalation=escalation,
            mutation_block=bool(item.get("mutation_block", False)),
            fail_closed=bool(item.get("fail_closed", False)),
        )
        if not clause.clause_id:
            raise CanonLawError("canon law clause missing clause_id")
        clauses[clause.clause_id] = clause
    return clauses


def one_way_escalation(current: str, requested: str) -> str:
    current_norm = _validate_escalation(current)
    requested_norm = _validate_escalation(requested)
    if ESCALATION_ORDER[requested_norm] < ESCALATION_ORDER[current_norm]:
        return current_norm
    return requested_norm


def violation_event_payload(*, component: str, clause: CanonClause, reason: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "component": component,
        "article": clause.article,
        "clause_id": clause.clause_id,
        "reason": reason,
        "escalation": clause.escalation,
        "mutation_block": clause.mutation_block,
        "fail_closed": clause.fail_closed,
        "context": dict(context or {}),
    }
    payload["payload_hash"] = sha256_prefixed_digest(canonical_json(payload))
    return payload


def emit_violation_event(*, component: str, clause: CanonClause, reason: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = violation_event_payload(component=component, clause=clause, reason=reason, context=context)
    tx_id = f"CANON-{component.upper()}-{clause.clause_id}"
    return append_tx(tx_type="governance_canon_violation", payload=payload, tx_id=tx_id)


__all__ = [
    "CANON_LAW_PATH",
    "ESCALATION_ORDER",
    "CanonClause",
    "CanonLawError",
    "emit_violation_event",
    "load_canon_law",
    "one_way_escalation",
    "violation_event_payload",
]
