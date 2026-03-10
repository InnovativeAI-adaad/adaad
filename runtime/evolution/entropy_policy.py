# SPDX-License-Identifier: Apache-2.0
"""Deterministic entropy ceiling policy enforcement."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from runtime.governance.foundation import sha256_prefixed_digest


class EntropyPolicyViolation(RuntimeError):
    """Raised when an entropy policy ceiling is exceeded."""

    def __init__(self, *, reason: str, detail: Dict[str, Any]) -> None:
        self.reason = str(reason)
        self.detail = dict(detail)
        super().__init__(self.reason)


@dataclass(frozen=True)
class EntropyAnomalyThresholds:
    """Deterministic anomaly triage thresholds for observed entropy bits.

    ``monitor_bits`` marks the first non-zero observed entropy level as an anomaly.
    ``investigate_bits`` marks the threshold where anomalies require manual triage.
    ``block_bits`` marks critical anomaly severity and always fail-closed behavior.
    """

    monitor_bits: int = 1
    investigate_bits: int = 8
    block_bits: int = 16

    def classify(self, *, observed_bits: int) -> Dict[str, str]:
        """Classify anomaly severity deterministically using integer thresholds."""
        observed = max(0, int(observed_bits))
        if observed >= int(self.block_bits):
            return {"triage_level": "block", "triage_reason": "anomaly_observed_bits_block_threshold_reached"}
        if observed >= int(self.investigate_bits):
            return {
                "triage_level": "investigate",
                "triage_reason": "anomaly_observed_bits_investigate_threshold_reached",
            }
        if observed >= int(self.monitor_bits):
            return {"triage_level": "monitor", "triage_reason": "anomaly_observed_bits_monitor_threshold_reached"}
        return {"triage_level": "none", "triage_reason": "anomaly_not_detected"}


@dataclass(frozen=True)
class EntropyAnomalyTriageThresholds:
    """Ratio-based triage thresholds for entropy budget utilisation (Phase 34).

    Classifies the highest utilisation ratio (max of mutation and epoch ratios)
    into one of four deterministic triage levels:

    - ``"ok"``       — below warning threshold
    - ``"warning"``  — at or above ``warning_ratio`` but below ``escalate_ratio``
    - ``"escalate"`` — at or above ``escalate_ratio`` but below ``critical_ratio``
    - ``"critical"`` — at or above ``critical_ratio``
    - ``"disabled"`` — policy disabled (returned when ``policy_enabled=False``)

    Parameters
    ----------
    warning_ratio:
        Utilisation ratio (0.0–1.0) above which triage is ``"warning"``.
    escalate_ratio:
        Utilisation ratio above which triage is ``"escalate"``.
    critical_ratio:
        Utilisation ratio above which triage is ``"critical"``.
    """

    warning_ratio:  float = 0.70
    escalate_ratio: float = 0.90
    critical_ratio: float = 1.00

    def classify(
        self,
        *,
        mutation_ratio: float,
        epoch_ratio: float,
        policy_enabled: bool = True,
    ) -> str:
        """Return the triage level string for the given utilisation ratios.

        Parameters
        ----------
        mutation_ratio:
            Fraction of the per-mutation ceiling consumed.
        epoch_ratio:
            Fraction of the per-epoch ceiling consumed.
        policy_enabled:
            When ``False``, returns ``"disabled"`` unconditionally.
        """
        if not policy_enabled:
            return "disabled"
        highest = max(float(mutation_ratio), float(epoch_ratio))
        if highest >= float(self.critical_ratio):
            return "critical"
        if highest >= float(self.escalate_ratio):
            return "escalate"
        if highest >= float(self.warning_ratio):
            return "warning"
        return "ok"


ENTROPY_REASON_TAXONOMY = {
    "ok",
    "entropy_policy_disabled",
    "entropy_budget_exceeded",
    "epoch_entropy_budget_exceeded",
    "mutation_and_epoch_entropy_budget_exceeded",
    "anomaly_not_detected",
    "anomaly_observed_bits_monitor_threshold_reached",
    "anomaly_observed_bits_investigate_threshold_reached",
    "anomaly_observed_bits_block_threshold_reached",
}


@dataclass(frozen=True)
class EntropyPolicy:
    policy_id: str
    per_mutation_ceiling_bits: int
    per_epoch_ceiling_bits: int
    anomaly_thresholds: EntropyAnomalyThresholds = field(default_factory=EntropyAnomalyThresholds)
    anomaly_triage: EntropyAnomalyTriageThresholds = field(default_factory=EntropyAnomalyTriageThresholds)

    @property
    def policy_hash(self) -> str:
        return sha256_prefixed_digest(
            {
                "policy_id": self.policy_id,
                "per_mutation_ceiling_bits": self.per_mutation_ceiling_bits,
                "per_epoch_ceiling_bits": self.per_epoch_ceiling_bits,
                "anomaly_thresholds": {
                    "monitor_bits": int(self.anomaly_thresholds.monitor_bits),
                    "investigate_bits": int(self.anomaly_thresholds.investigate_bits),
                    "block_bits": int(self.anomaly_thresholds.block_bits),
                },
            }
        )

    def enforce(
        self,
        *,
        mutation_bits: int,
        epoch_bits: int,
        declared_bits: int | None = None,
        observed_bits: int = 0,
    ) -> Dict[str, Any]:
        """Enforce mutation/epoch entropy ceilings.

        When ``declared_bits`` is omitted, the method treats ``mutation_bits`` as the
        caller-provided declared baseline and computes ``mutation_bits`` detail as
        ``declared_bits + observed_bits``. Callers that already combined observed bits
        into ``mutation_bits`` should pass ``declared_bits`` explicitly to avoid
        double-counting.
        """
        effective_declared_bits = int(mutation_bits if declared_bits is None else declared_bits)
        effective_observed_bits = max(0, int(observed_bits))
        mutation_total_bits = effective_declared_bits + effective_observed_bits
        effective_epoch_bits = int(epoch_bits)

        detail = {
            "declared_bits": effective_declared_bits,
            "observed_bits": effective_observed_bits,
            "mutation_bits": mutation_total_bits,
            "epoch_bits": effective_epoch_bits,
            "policy_id": self.policy_id,
            "policy_hash": self.policy_hash,
            "per_mutation_ceiling_bits": int(self.per_mutation_ceiling_bits),
            "per_epoch_ceiling_bits": int(self.per_epoch_ceiling_bits),
            "anomaly_thresholds": {
                "monitor_bits": int(self.anomaly_thresholds.monitor_bits),
                "investigate_bits": int(self.anomaly_thresholds.investigate_bits),
                "block_bits": int(self.anomaly_thresholds.block_bits),
            },
        }
        detail.update(self.anomaly_thresholds.classify(observed_bits=effective_observed_bits))

        policy_enabled = int(self.per_mutation_ceiling_bits) > 0 and int(self.per_epoch_ceiling_bits) > 0
        if not policy_enabled:
            return {
                "passed": True,
                "reason": "entropy_policy_disabled",
                **detail,
                "triage_level": "disabled",  # overrides anomaly_thresholds triage in detail
            }

        mutation_ratio = mutation_total_bits / float(self.per_mutation_ceiling_bits)
        epoch_ratio = effective_epoch_bits / float(self.per_epoch_ceiling_bits)
        detail["mutation_utilization_ratio"] = mutation_ratio
        detail["epoch_utilization_ratio"] = epoch_ratio
        detail["triage_level"] = self.anomaly_triage.classify(
            mutation_ratio=mutation_ratio,
            epoch_ratio=epoch_ratio,
            policy_enabled=True,
        )

        mutation_exceeded = mutation_total_bits > int(self.per_mutation_ceiling_bits)
        epoch_exceeded = effective_epoch_bits > int(self.per_epoch_ceiling_bits)
        if mutation_exceeded or epoch_exceeded:
            if mutation_exceeded and epoch_exceeded:
                reason = "mutation_and_epoch_entropy_budget_exceeded"
            elif mutation_exceeded:
                reason = "entropy_budget_exceeded"
            else:
                reason = "epoch_entropy_budget_exceeded"
            raise EntropyPolicyViolation(reason=reason, detail=detail)

        return {"passed": True, "reason": "ok", **detail}


def enforce_entropy_policy(
    *,
    policy: EntropyPolicy,
    mutation_bits: int,
    epoch_bits: int,
    declared_bits: int | None = None,
    observed_bits: int = 0,
) -> Dict[str, Any]:
    """Deprecated adapter returning verdict dictionaries without raising."""
    try:
        return policy.enforce(
            mutation_bits=mutation_bits,
            epoch_bits=epoch_bits,
            declared_bits=declared_bits,
            observed_bits=observed_bits,
        )
    except EntropyPolicyViolation as exc:
        return {
            "passed": False,
            "reason": "entropy_ceiling_exceeded",
            "violation_reason": exc.reason,
            **exc.detail,
        }


__all__ = [
    "ENTROPY_REASON_TAXONOMY",
    "EntropyAnomalyThresholds",
    "EntropyAnomalyTriageThresholds",
    "EntropyPolicy",
    "EntropyPolicyViolation",
    "enforce_entropy_policy",
]
