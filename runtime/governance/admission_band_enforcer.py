# SPDX-License-Identifier: Apache-2.0
"""AdmissionBandEnforcer — ADAAD Phase 28, PR-28-01.

Wires the advisory AdmissionDecision (Phase 25) into the constitution's
pre-filter layer, enabling escalation to blocking via
ADAAD_SEVERITY_ESCALATIONS.

Design invariants
─────────────────
- ``advisory_only = True`` by default.  GovernanceGate retains sole actual
  mutation-approval authority when this enforcer operates in advisory mode.
- When ``ADAAD_SEVERITY_ESCALATIONS`` contains
  ``{"admission_band_enforcement": "blocking"}``, HALT-band decisions block
  the proposal from reaching GovernanceGate (emergency stop only).
- Deterministic: identical (health_score, risk_score, escalation_config)
  → identical EnforcerVerdict → identical verdict_digest.
- Fail-safe: any exception in health computation defaults to GREEN-band
  admission so the pipeline never silently stalls.
- Never imports or calls GovernanceGate — authority boundary is structural.

Escalation levels
─────────────────
  advisory  (default)  — EnforcerVerdict.blocked is always False; verdict
                         is appended to the pipeline audit trail only.
  blocking             — EnforcerVerdict.blocked = True when band == 'halt';
                         amber/red bands remain advisory even when escalated.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from runtime.governance.mutation_admission import (
    AdmissionDecision,
    MutationAdmissionController,
)

log = logging.getLogger(__name__)

ENFORCER_VERSION: str = "28.0"

# Escalation env-var key and value
_ESCALATION_ENV_VAR: str = "ADAAD_SEVERITY_ESCALATIONS"
_ESCALATION_RULE_KEY: str = "admission_band_enforcement"
_ESCALATION_BLOCKING_VALUE: str = "blocking"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EnforcerVerdict:
    """Deterministic admission band enforcement verdict.

    Attributes
    ----------
    decision:
        Underlying AdmissionDecision from MutationAdmissionController.
    escalation_mode:
        ``"advisory"`` | ``"blocking"`` — resolved at construction time.
    blocked:
        ``True`` only when ``escalation_mode == "blocking"`` and
        ``decision.admission_band == "halt"``.  Always ``False`` in advisory
        mode regardless of band.
    block_reason:
        Human-readable reason when ``blocked`` is True; empty string otherwise.
    verdict_digest:
        SHA-256 of the canonical JSON of this verdict (excluding digest itself).
    enforcer_version:
        Module version string for ledger traceability.
    """

    decision: AdmissionDecision
    escalation_mode: str
    blocked: bool
    block_reason: str
    verdict_digest: str
    enforcer_version: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "decision": {
                "health_score":     self.decision.health_score,
                "mutation_risk_score": self.decision.mutation_risk_score,
                "admission_band":   self.decision.admission_band,
                "admitted":         self.decision.admitted,
                "advisory_only":    self.decision.advisory_only,
                "risk_threshold":   self.decision.risk_threshold,
                "epoch_paused":     self.decision.epoch_paused,
                "deferral_reason":  self.decision.deferral_reason,
                "decision_digest":  self.decision.decision_digest,
                "controller_version": self.decision.controller_version,
            },
            "escalation_mode":  self.escalation_mode,
            "blocked":          self.blocked,
            "block_reason":     self.block_reason,
            "verdict_digest":   self.verdict_digest,
            "enforcer_version": self.enforcer_version,
        }


# ---------------------------------------------------------------------------
# Enforcer
# ---------------------------------------------------------------------------

class AdmissionBandEnforcer:
    """Translate AdmissionDecision into a pipeline-level enforcement verdict.

    Parameters
    ----------
    health_score:
        Current GovernanceHealthAggregator composite score ∈ [0.0, 1.0].
        If ``None``, defaults to GREEN-band (1.0) for fail-safe operation.
    escalation_mode:
        Override escalation mode.  If ``None`` (default), resolved from
        ``ADAAD_SEVERITY_ESCALATIONS`` env var.
    """

    def __init__(
        self,
        *,
        health_score: Optional[float] = None,
        escalation_mode: Optional[str] = None,
    ) -> None:
        self._health_score = health_score
        self._escalation_mode = escalation_mode or self._resolve_escalation_mode()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, mutation_risk_score: float) -> EnforcerVerdict:
        """Produce a deterministic EnforcerVerdict for ``mutation_risk_score``.

        Parameters
        ----------
        mutation_risk_score:
            Candidate mutation risk score ∈ [0.0, 1.0].

        Returns
        -------
        EnforcerVerdict
            Always returns; never raises.
        """
        health = self._safe_health_score()
        try:
            controller = MutationAdmissionController()
            decision: AdmissionDecision = controller.evaluate(health, mutation_risk_score)
        except Exception as exc:  # pragma: no cover
            log.error("AdmissionBandEnforcer: controller.evaluate failed: %s", exc)
            # Fail-safe: permissive green-band advisory decision
            controller = MutationAdmissionController()
            decision = controller.evaluate(1.0, mutation_risk_score)

        blocked, block_reason = self._apply_escalation(decision)

        verdict_digest = self._compute_digest(decision, blocked, block_reason)

        return EnforcerVerdict(
            decision=decision,
            escalation_mode=self._escalation_mode,
            blocked=blocked,
            block_reason=block_reason,
            verdict_digest=verdict_digest,
            enforcer_version=ENFORCER_VERSION,
        )

    @property
    def escalation_mode(self) -> str:
        return self._escalation_mode

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _safe_health_score(self) -> float:
        """Return health score, defaulting to 1.0 (GREEN) on any problem."""
        if self._health_score is None:
            return 1.0
        try:
            h = float(self._health_score)
            return max(0.0, min(1.0, h))
        except (TypeError, ValueError):
            log.warning("AdmissionBandEnforcer: invalid health_score; defaulting to 1.0")
            return 1.0

    def _apply_escalation(
        self, decision: AdmissionDecision
    ) -> tuple[bool, str]:
        """Return (blocked, block_reason) based on mode and decision band."""
        if self._escalation_mode != _ESCALATION_BLOCKING_VALUE:
            return False, ""
        # Blocking mode: only HALT band triggers a hard block
        if decision.admission_band == "halt":
            return (
                True,
                (
                    "Admission band enforcement escalated to blocking: "
                    "governance health catastrophic (< 0.40); "
                    "mutation proposal blocked. "
                    "Restore governance health before retrying."
                ),
            )
        return False, ""

    @staticmethod
    def _resolve_escalation_mode() -> str:
        """Parse ADAAD_SEVERITY_ESCALATIONS env var for the admission rule."""
        raw = os.getenv(_ESCALATION_ENV_VAR, "").strip()
        if not raw:
            return "advisory"
        try:
            mapping = json.loads(raw)
            value = mapping.get(_ESCALATION_RULE_KEY, "advisory")
            return value if value in ("advisory", "blocking") else "advisory"
        except (json.JSONDecodeError, AttributeError):
            log.warning(
                "AdmissionBandEnforcer: could not parse %s; defaulting to advisory",
                _ESCALATION_ENV_VAR,
            )
            return "advisory"

    @staticmethod
    def _compute_digest(
        decision: AdmissionDecision,
        blocked: bool,
        block_reason: str,
    ) -> str:
        payload = json.dumps(
            {
                "decision_digest":  decision.decision_digest,
                "blocked":          blocked,
                "block_reason":     block_reason,
                "enforcer_version": ENFORCER_VERSION,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()


__all__ = ["AdmissionBandEnforcer", "EnforcerVerdict", "ENFORCER_VERSION"]
