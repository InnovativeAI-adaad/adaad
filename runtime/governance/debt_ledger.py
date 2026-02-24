# SPDX-License-Identifier: Apache-2.0
"""Deterministic governance warning debt accumulation and decay."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, Mapping

from runtime import metrics
from runtime.governance.foundation import ZERO_HASH, canonical_json_bytes, sha256_prefixed_digest
from security.ledger.journal import append_tx, write_entry

GOVERNANCE_DEBT_EVENT_TYPE = "governance_debt_snapshot"
DEBT_LEDGER_SCHEMA_VERSION = "1.0"
DEFAULT_WARNING_WEIGHTS: Dict[str, float] = {
    "max_mutation_rate": 1.25,
    "import_smoke_test": 1.0,
    "coverage_regression": 1.0,
    "resource_bounds": 0.75,
    "entropy_budget_limit": 1.5,
    "governance_drift_detected": 1.25,
}


@dataclass(frozen=True)
class GovernanceDebtSnapshot:
    schema_version: str
    epoch_id: str
    epoch_index: int
    warning_count: int
    warning_weighted_sum: float
    applied_decay_epochs: int
    decayed_prior_debt: float
    compound_debt_score: float
    breach_threshold: float
    threshold_breached: bool
    warning_weights: Dict[str, float]
    warning_rules: list[str]
    prev_snapshot_hash: str
    snapshot_hash: str


class GovernanceDebtLedger:
    """Append-only, deterministic governance debt tracker keyed by epoch index."""

    def __init__(
        self,
        *,
        warning_weights: Mapping[str, float] | None = None,
        decay_per_epoch: float = 0.9,
        breach_threshold: float = 3.0,
    ) -> None:
        self.warning_weights = {k: float(v) for k, v in (warning_weights or DEFAULT_WARNING_WEIGHTS).items()}
        self.decay_per_epoch = min(1.0, max(0.0, float(decay_per_epoch)))
        self.breach_threshold = max(0.0, float(breach_threshold))
        self._last_snapshot: GovernanceDebtSnapshot | None = None

    @property
    def last_snapshot(self) -> GovernanceDebtSnapshot | None:
        return self._last_snapshot

    def accumulate_epoch_verdicts(
        self,
        *,
        epoch_id: str,
        epoch_index: int,
        warning_verdicts: Iterable[Mapping[str, Any]],
        agent_id: str = "system",
    ) -> GovernanceDebtSnapshot:
        prev_snapshot_hash = self._last_snapshot.snapshot_hash if self._last_snapshot else ZERO_HASH
        previous_index = self._last_snapshot.epoch_index if self._last_snapshot else None
        decay_epochs = 0 if previous_index is None else max(0, int(epoch_index) - int(previous_index))
        prior_compound = float(self._last_snapshot.compound_debt_score) if self._last_snapshot else 0.0
        decayed_prior = prior_compound * (self.decay_per_epoch ** decay_epochs)

        warning_rows = []
        for verdict in warning_verdicts:
            rule_name = str(verdict.get("rule") or "unknown")
            weight = float(self.warning_weights.get(rule_name, 1.0))
            warning_rows.append((rule_name, weight))

        warning_weighted_sum = round(sum(weight for _, weight in warning_rows), 6)
        compound = round(decayed_prior + warning_weighted_sum, 6)
        threshold_breached = compound >= self.breach_threshold if self.breach_threshold > 0.0 else False

        base_payload: Dict[str, Any] = {
            "schema_version": DEBT_LEDGER_SCHEMA_VERSION,
            "epoch_id": str(epoch_id),
            "epoch_index": int(epoch_index),
            "warning_count": len(warning_rows),
            "warning_weighted_sum": warning_weighted_sum,
            "applied_decay_epochs": decay_epochs,
            "decayed_prior_debt": round(decayed_prior, 6),
            "compound_debt_score": compound,
            "breach_threshold": self.breach_threshold,
            "threshold_breached": threshold_breached,
            "warning_weights": {rule: round(weight, 6) for rule, weight in sorted(warning_rows)},
            "warning_rules": sorted(rule for rule, _ in warning_rows),
            "prev_snapshot_hash": prev_snapshot_hash,
        }
        snapshot_hash = sha256_prefixed_digest(canonical_json_bytes(base_payload))
        snapshot = GovernanceDebtSnapshot(snapshot_hash=snapshot_hash, **base_payload)
        self._last_snapshot = snapshot

        payload = asdict(snapshot)
        metrics.log(event_type=GOVERNANCE_DEBT_EVENT_TYPE, payload=payload, level="WARNING" if threshold_breached else "INFO")
        write_entry(agent_id=agent_id or "system", action=GOVERNANCE_DEBT_EVENT_TYPE, payload=payload)
        append_tx(tx_type=GOVERNANCE_DEBT_EVENT_TYPE, payload=payload)
        return snapshot


__all__ = [
    "GOVERNANCE_DEBT_EVENT_TYPE",
    "DEBT_LEDGER_SCHEMA_VERSION",
    "DEFAULT_WARNING_WEIGHTS",
    "GovernanceDebtSnapshot",
    "GovernanceDebtLedger",
]
