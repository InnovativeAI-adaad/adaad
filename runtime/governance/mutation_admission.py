# SPDX-License-Identifier: Apache-2.0
"""MutationAdmissionController — ADAAD Phase 25.

Translates GovernanceHealthAggregator health_score into an advisory
AdmissionDecision: a per-mutation recommendation on whether a candidate
should be admitted to the evolution pipeline for the current epoch.

Design invariants
─────────────────
- ALL output is advisory. ``advisory_only`` is structurally ``True``; no
  runtime path may set it to ``False``. GovernanceGate retains sole actual
  mutation-approval authority.
- Deterministic: identical (health_score, mutation_risk_score) → identical
  AdmissionDecision → identical decision_digest.
- Fail-safe: out-of-range inputs are clamped, never raised.
- ``epoch_paused`` is advisory only — it signals a catastrophic health
  degradation recommendation; the operator and GovernanceGate decide action.
- ``risk_threshold`` defines the exclusive upper bound on mutation_risk_score
  for admission in the current health band.

Health band / risk threshold mapping (constitutional)
──────────────────────────────────────────────────────
  Band   health_score range    risk_threshold  admits_all  epoch_paused
  ────── ─────────────────── ──────────────── ─────────── ────────────
  GREEN  h >= GREEN_FLOOR     1.01 (all pass)  True        False
  AMBER  AMBER_FLOOR <= h     0.60             False       False
         < GREEN_FLOOR
  RED    RED_FLOOR <= h        0.35             False       False
         < AMBER_FLOOR
  HALT   h < RED_FLOOR         0.00 (none)     False       True (advisory)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

CONTROLLER_VERSION: str = "25.0"

# Health band boundaries (match GovernanceHealthAggregator thresholds)
GREEN_FLOOR: float = 0.80
AMBER_FLOOR: float = 0.60   # == HEALTH_DEGRADED_THRESHOLD
RED_FLOOR:   float = 0.40   # catastrophic advisory halt threshold

# Risk thresholds per band — exclusive upper bound on mutation_risk_score
_RISK_THRESHOLD_GREEN: float = 1.01   # admits all (> any valid risk score)
_RISK_THRESHOLD_AMBER: float = 0.60
_RISK_THRESHOLD_RED:   float = 0.35
_RISK_THRESHOLD_HALT:  float = 0.00   # admits none

_DEFERRAL_REASONS = {
    "amber": "Governance health degraded (amber): high-risk mutations deferred; risk_score must be < 0.60.",
    "red":   "Governance health degraded (red): only low-risk mutations admitted; risk_score must be < 0.35.",
    "halt":  "Governance health catastrophic (< 0.40): epoch pause advisory issued; no mutations admitted.",
}


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AdmissionDecision:
    """Advisory mutation admission decision derived from governance health.

    All fields are deterministic given the same (health_score, mutation_risk_score).

    Attributes
    ----------
    health_score:
        Clamped composite h ∈ [0.0, 1.0] used for band classification.
    mutation_risk_score:
        Clamped mutation candidate risk ∈ [0.0, 1.0] evaluated against threshold.
    admission_band:
        ``"green"`` | ``"amber"`` | ``"red"`` | ``"halt"`` — health band at
        decision time.
    risk_threshold:
        Exclusive upper bound on ``mutation_risk_score`` for admission.
        Mutations with ``risk_score >= risk_threshold`` are not admitted.
    admitted:
        ``True`` when ``mutation_risk_score < risk_threshold`` and not halted.
    admits_all:
        ``True`` only in GREEN band — shorthand: risk_threshold admits every
        valid risk score.
    epoch_paused:
        Advisory flag. ``True`` when health_score < RED_FLOOR. GovernanceGate
        and human operator decide actual response.
    deferral_reason:
        Human-readable reason for non-admission; ``None`` when admitted.
    advisory_only:
        Structural invariant. Always ``True``. GovernanceGate is never bypassed.
    decision_digest:
        SHA-256(health_score | mutation_risk_score | admission_band | admitted |
                epoch_paused | risk_threshold | controller_version).
    controller_version:
        Semver string identifying the controller implementation.
    """

    health_score:        float
    mutation_risk_score: float
    admission_band:      str
    risk_threshold:      float
    admitted:            bool
    admits_all:          bool
    epoch_paused:        bool
    deferral_reason:     str | None
    advisory_only:       bool
    decision_digest:     str
    controller_version:  str


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class MutationAdmissionController:
    """Translate governance health score into per-mutation admission decisions.

    Usage
    -----
    ::

        controller = MutationAdmissionController()
        decision = controller.evaluate(
            health_score=aggregator.compute(epoch_id).health_score,
            mutation_risk_score=risk_scorer.score(mutation),
        )
        if not decision.admitted:
            defer(mutation, reason=decision.deferral_reason)

    GovernanceGate isolation
    ────────────────────────
    ``MutationAdmissionController`` **never** imports or calls ``GovernanceGate``.
    It is an advisory signal only. Gate authority remains with GovernanceGate
    through the established gate chain.
    """

    def evaluate(
        self,
        health_score: float,
        mutation_risk_score: float,
    ) -> AdmissionDecision:
        """Produce a deterministic AdmissionDecision for one mutation candidate.

        Parameters
        ----------
        health_score:
            Composite governance health h ∈ [0.0, 1.0].  Values outside range
            are clamped; no exception is raised (fail-safe).
        mutation_risk_score:
            Mutation risk score ∈ [0.0, 1.0].  Values outside range are clamped.

        Returns
        -------
        AdmissionDecision
            Fully deterministic; digest covers all output fields.
        """
        h = max(0.0, min(1.0, float(health_score)))
        r = max(0.0, min(1.0, float(mutation_risk_score)))

        band, risk_threshold, admits_all, epoch_paused = self._classify(h)

        admitted = (not epoch_paused) and (r < risk_threshold)

        if admitted:
            deferral_reason = None
        elif epoch_paused:
            deferral_reason = _DEFERRAL_REASONS["halt"]
        else:
            deferral_reason = _DEFERRAL_REASONS.get(band, "Mutation not admitted.")

        digest = self._compute_digest(
            h, r, band, admitted, epoch_paused, risk_threshold
        )

        return AdmissionDecision(
            health_score=h,
            mutation_risk_score=r,
            admission_band=band,
            risk_threshold=risk_threshold,
            admitted=admitted,
            admits_all=admits_all,
            epoch_paused=epoch_paused,
            deferral_reason=deferral_reason,
            advisory_only=True,         # structural invariant — never False
            decision_digest=digest,
            controller_version=CONTROLLER_VERSION,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify(
        h: float,
    ) -> tuple[str, float, bool, bool]:
        """Return (band, risk_threshold, admits_all, epoch_paused)."""
        if h >= GREEN_FLOOR:
            return "green", _RISK_THRESHOLD_GREEN, True,  False
        if h >= AMBER_FLOOR:
            return "amber", _RISK_THRESHOLD_AMBER, False, False
        if h >= RED_FLOOR:
            return "red",   _RISK_THRESHOLD_RED,   False, False
        return "halt", _RISK_THRESHOLD_HALT, False, True

    @staticmethod
    def _compute_digest(
        h: float,
        r: float,
        band: str,
        admitted: bool,
        epoch_paused: bool,
        risk_threshold: float,
    ) -> str:
        payload = json.dumps(
            {
                "health_score":        round(h, 10),
                "mutation_risk_score": round(r, 10),
                "admission_band":      band,
                "admitted":            admitted,
                "epoch_paused":        epoch_paused,
                "risk_threshold":      round(risk_threshold, 10),
                "controller_version":  CONTROLLER_VERSION,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
