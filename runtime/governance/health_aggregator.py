# SPDX-License-Identifier: Apache-2.0
"""GovernanceHealthAggregator — ADAAD Phase 8, PR-8-01.

Computes a deterministic composite Governance Health Score ``h ∈ [0.0, 1.0]``
from four live signals sourced from Phases 5–7:

    Signal                       Weight  Source
    ─────────────────────────────────────────────────────────────────────
    avg_reviewer_reputation      0.30    ReviewerReputationLedger (Ph.7)
    amendment_gate_pass_rate     0.25    RoadmapAmendmentEngine (Ph.6)
    federation_divergence_clean  0.25    FederatedEvidenceMatrix (Ph.5)
    epoch_health_score           0.20    EpochTelemetry (core pipeline)

``h < 0.60`` emits ``governance_health_degraded.v1`` journal event and
triggers Aponi alert.

Authority invariants
──────────────────────
- GovernanceHealthAggregator is **advisory only**.  ``h`` never gates,
  approves, or blocks mutations.  GovernanceGate retains sole authority.
- No single signal can drive ``h`` to 0.0 or 1.0 — weight sums to 1.0
  but each signal is independently clamped to ``[0.0, 1.0]``.
- Deterministic: identical signal inputs → identical ``h``.
- Epoch-scoped: weight vector snapshotted per epoch for replay safety.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from runtime.constitution import CONSTITUTION_VERSION
from runtime.evolution.scoring_algorithm import ALGORITHM_VERSION

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Signal weights — constitutional invariant: must sum to 1.0
# ---------------------------------------------------------------------------

SIGNAL_WEIGHTS: Dict[str, float] = {
    "avg_reviewer_reputation":          0.18,  # Phase 7   (-0.01 rebalance for Ph.35)
    "amendment_gate_pass_rate":         0.16,  # Phase 6   (-0.01 rebalance for Ph.35)
    "federation_divergence_clean":      0.16,  # Phase 5   (-0.01 rebalance for Ph.35)
    "epoch_health_score":               0.12,  # core      (unchanged)
    "routing_health_score":             0.10,  # Phase 23  (unchanged)
    "admission_rate_score":             0.09,  # Phase 26  (unchanged)
    "governance_debt_health_score":     0.08,  # Phase 32  (-0.01 rebalance for Ph.35)
    "certifier_rejection_rate_score":   0.06,  # Phase 33  (-0.01 rebalance for Ph.35)
    "gate_approval_rate_score":         0.05,  # Phase 35  (new — GateDecisionLedger)
}
# Weight sum invariant: 0.18+0.16+0.16+0.12+0.10+0.09+0.08+0.06+0.05 = 1.00 ✅

HEALTH_DEGRADED_THRESHOLD: float = 0.60
_WEIGHT_SUM_TOLERANCE: float = 1e-9

JOURNAL_EVENT_SNAPSHOT  = "governance_health_snapshot.v1"
JOURNAL_EVENT_DEGRADED  = "governance_health_degraded.v1"

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class HealthSnapshot:
    """Immutable result of one GovernanceHealthAggregator computation."""

    epoch_id:                  str
    health_score:              float                # h ∈ [0.0, 1.0]
    signal_breakdown:          Dict[str, float]     # signal_id → raw value
    weight_snapshot:           Dict[str, float]     # signal_id → weight used
    weight_snapshot_digest:    str                  # sha256 of canonical weights
    constitution_version:      str
    scoring_algorithm_version: str
    degraded:                  bool                 # h < HEALTH_DEGRADED_THRESHOLD
    # Phase 23: routing health signal detail (None when no engine wired)
    routing_health_report:     Optional[Dict[str, Any]] = None
    # Phase 26: admission rate signal detail (None when no tracker wired)
    admission_rate_report:     Optional[Dict[str, Any]] = None
    # Phase 32: governance debt signal detail (None when no ledger wired)
    debt_report:               Optional[Dict[str, Any]] = None
    # Phase 33: certifier rejection rate detail (None when no reader wired)
    certifier_report:          Optional[Dict[str, Any]] = None
    # Phase 35: gate decision approval rate detail (None when no reader wired)
    gate_decision_report:      Optional[Dict[str, Any]] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


class GovernanceHealthAggregator:
    """Compute epoch-scoped governance health from live Phase 5–7 signals.

    Parameters
    ----------
    reviewer_reputation_ledger:
        Instance of ``ReviewerReputationLedger`` (Phase 7).  When ``None``
        the signal defaults to ``0.0`` with a warning.
    roadmap_amendment_engine:
        Instance of ``RoadmapAmendmentEngine`` (Phase 6).  ``None`` → 0.0.
    federated_evidence_matrix:
        Instance of ``FederatedEvidenceMatrix`` (Phase 5).  ``None`` → 1.0
        (single-node fallback: no federation = no divergence).
    epoch_telemetry:
        Instance of ``EpochTelemetry`` (core).  ``None`` → 0.0.
    journal_emit:
        Optional callable ``(event_type: str, payload: dict) → None`` for
        ledger event emission.  Defaults to ``security.ledger.journal.append_tx``.
    weights:
        Override signal weights (must sum to 1.0 within tolerance).  Defaults
        to ``SIGNAL_WEIGHTS``.
    """

    def __init__(
        self,
        *,
        reviewer_reputation_ledger=None,
        roadmap_amendment_engine=None,
        federated_evidence_matrix=None,
        epoch_telemetry=None,
        journal_emit=None,
        weights: Optional[Dict[str, float]] = None,
        routing_analytics_engine=None,
        admission_tracker=None,       # Phase 26
        debt_ledger=None,             # Phase 32
        certifier_scan_reader=None,   # Phase 33
        gate_decision_reader=None,    # Phase 35
    ) -> None:
        self._reputation_ledger    = reviewer_reputation_ledger
        self._amendment_engine     = roadmap_amendment_engine
        self._evidence_matrix      = federated_evidence_matrix
        self._epoch_telemetry      = epoch_telemetry
        self._journal_emit         = journal_emit or self._default_journal_emit
        self._routing_engine       = routing_analytics_engine  # Phase 23
        self._admission_tracker    = admission_tracker          # Phase 26
        self._debt_ledger          = debt_ledger                # Phase 32
        self._certifier_reader     = certifier_scan_reader      # Phase 33
        self._gate_decision_reader = gate_decision_reader       # Phase 35

        # Validate and snapshot weights
        self._weights = dict(weights or SIGNAL_WEIGHTS)
        self._validate_weights(self._weights)
        self._weight_digest = self._digest_weights(self._weights)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(self, epoch_id: str) -> HealthSnapshot:
        """Compute health snapshot for ``epoch_id``.

        Returns a deterministic ``HealthSnapshot``.  Emits ledger events.
        Side-effects (journal write failures) never raise — they are logged
        and skipped.
        """
        breakdown = self._collect_signals(epoch_id)
        h = self._weighted_sum(breakdown)

        # Phase 23: capture routing health report detail for snapshot
        _routing_report_dict: Optional[Dict[str, Any]] = None
        if self._routing_engine is not None:
            try:
                _rhr = self._routing_engine.generate_report()
                _routing_report_dict = {
                    "status": _rhr.status,
                    "health_score": _rhr.health_score,
                    "dominant_strategy": _rhr.dominant_strategy,
                    "report_digest": _rhr.report_digest,
                    "available": True,
                }
            except Exception:
                pass

        # Phase 26: capture admission rate report detail for snapshot
        _admission_report_dict: Optional[Dict[str, Any]] = None
        if self._admission_tracker is not None:
            try:
                _arr = self._admission_tracker.generate_report()
                _admission_report_dict = {
                    "admission_rate_score": _arr.admission_rate_score,
                    "admitted_count":       _arr.admitted_count,
                    "total_count":          _arr.total_count,
                    "epochs_in_window":     _arr.epochs_in_window,
                    "report_digest":        _arr.report_digest,
                    "available":            True,
                }
            except Exception:
                pass

        # Phase 32: capture governance debt report detail for snapshot
        _debt_report_dict: Optional[Dict[str, Any]] = None
        if self._debt_ledger is not None:
            try:
                snap = self._debt_ledger.last_snapshot
                if snap is not None:
                    _debt_report_dict = {
                        "compound_debt_score":  snap.compound_debt_score,
                        "breach_threshold":     snap.breach_threshold,
                        "threshold_breached":   snap.threshold_breached,
                        "warning_count":        snap.warning_count,
                        "snapshot_hash":        snap.snapshot_hash,
                        "available":            True,
                    }
            except Exception:
                pass

        # Phase 33: capture certifier rejection rate detail for snapshot
        _certifier_report_dict: Optional[Dict[str, Any]] = None
        if self._certifier_reader is not None:
            try:
                rejection_rate = self._certifier_reader.rejection_rate()
                mutation_blocked = self._certifier_reader.mutation_blocked_count()
                _certifier_report_dict = {
                    "rejection_rate":      rejection_rate,
                    "certification_rate":  round(1.0 - rejection_rate, 6),
                    "mutation_blocked_count": mutation_blocked,
                    "available":           True,
                }
            except Exception:
                pass

        # Phase 35: capture gate decision approval rate detail for snapshot
        _gate_decision_report_dict: Optional[Dict[str, Any]] = None
        if self._gate_decision_reader is not None:
            try:
                approval_rate = self._gate_decision_reader.approval_rate()
                override_count = self._gate_decision_reader.human_override_count()
                _gate_decision_report_dict = {
                    "approval_rate":         approval_rate,
                    "rejection_rate":        round(1.0 - approval_rate, 6),
                    "human_override_count":  override_count,
                    "available":             True,
                }
            except Exception:
                pass

        snapshot = HealthSnapshot(
            epoch_id=epoch_id,
            health_score=h,
            signal_breakdown=dict(breakdown),
            weight_snapshot=dict(self._weights),
            weight_snapshot_digest=self._weight_digest,
            constitution_version=CONSTITUTION_VERSION,
            scoring_algorithm_version=ALGORITHM_VERSION,
            degraded=(h < HEALTH_DEGRADED_THRESHOLD),
            routing_health_report=_routing_report_dict,
            admission_rate_report=_admission_report_dict,
            debt_report=_debt_report_dict,
            certifier_report=_certifier_report_dict,
            gate_decision_report=_gate_decision_report_dict,
        )

        self._emit_snapshot(snapshot)

        if snapshot.degraded:
            self._emit_degraded(snapshot)

        return snapshot

    # ------------------------------------------------------------------
    # Signal collectors
    # ------------------------------------------------------------------

    def _collect_signals(self, epoch_id: str) -> Dict[str, float]:
        return {
            "avg_reviewer_reputation":          self._collect_reputation(epoch_id),
            "amendment_gate_pass_rate":         self._collect_amendment_rate(),
            "federation_divergence_clean":      self._collect_federation_clean(),
            "epoch_health_score":               self._collect_epoch_health(),
            "routing_health_score":             self._collect_routing_health(),           # Phase 23
            "admission_rate_score":             self._collect_admission_rate(),           # Phase 26
            "governance_debt_health_score":     self._collect_debt_health(),             # Phase 32
            "certifier_rejection_rate_score":   self._collect_certifier_health(),        # Phase 33
            "gate_approval_rate_score":         self._collect_gate_approval_health(),    # Phase 35
        }

    def _collect_reputation(self, epoch_id: str) -> float:
        if self._reputation_ledger is None:
            log.warning("GovernanceHealthAggregator: no reputation ledger; avg_reviewer_reputation=0.0")
            return 0.0
        try:
            entries = self._reputation_ledger.get_all_entries()
            if not entries:
                return 0.0
            # Filter to this epoch if epoch_id is present on entries
            epoch_entries = [e for e in entries if getattr(e, "epoch_id", None) == epoch_id]
            target = epoch_entries if epoch_entries else entries
            scores = [getattr(e, "composite_score", 0.0) for e in target if hasattr(e, "composite_score")]
            if not scores:
                return 0.0
            return min(1.0, max(0.0, sum(scores) / len(scores)))
        except Exception as exc:  # pragma: no cover
            log.warning("GovernanceHealthAggregator: reputation collection error: %s", exc)
            return 0.0

    def _collect_amendment_rate(self) -> float:
        if self._amendment_engine is None:
            log.warning("GovernanceHealthAggregator: no amendment engine; amendment_gate_pass_rate=0.0")
            return 0.0
        try:
            pending = self._amendment_engine.list_pending()
            # 0 pending proposals → gates are passing (score = 1.0)
            # >0 pending → proportional degradation; capped at 0.0 for 5+
            pending_count = len(pending)
            if pending_count == 0:
                return 1.0
            return min(1.0, max(0.0, 1.0 - (pending_count * 0.20)))
        except Exception as exc:  # pragma: no cover
            log.warning("GovernanceHealthAggregator: amendment rate error: %s", exc)
            return 0.0

    def _collect_federation_clean(self) -> float:
        if self._evidence_matrix is None:
            # Single-node: no federation configured — treat as clean (1.0)
            return 1.0
        try:
            return 1.0 if self._evidence_matrix.divergence_count == 0 else 0.0
        except Exception as exc:  # pragma: no cover
            log.warning("GovernanceHealthAggregator: federation clean error: %s", exc)
            return 0.0

    def _collect_epoch_health(self) -> float:
        if self._epoch_telemetry is None:
            log.warning("GovernanceHealthAggregator: no epoch telemetry; epoch_health_score=0.0")
            return 0.0
        try:
            indicators = self._epoch_telemetry.health_indicators()
            healthy = sum(
                1 for v in indicators.values()
                if isinstance(v, dict) and v.get("status") == "healthy"
            )
            total = sum(
                1 for v in indicators.values()
                if isinstance(v, dict) and v.get("status") in {"healthy", "warning"}
            )
            if total == 0:
                return 0.0
            return min(1.0, max(0.0, healthy / total))
        except Exception as exc:  # pragma: no cover
            log.warning("GovernanceHealthAggregator: epoch health error: %s", exc)
            return 0.0

    def _collect_routing_health(self) -> float:
        """Phase 23: Collect routing health signal from StrategyAnalyticsEngine.

        Default is 1.0 (full contribution) when no engine is wired — same
        convention as federation_divergence_clean for single-node deployments.
        """
        if self._routing_engine is None:
            return 1.0
        try:
            report = self._routing_engine.generate_report()
            return float(max(0.0, min(1.0, report.health_score)))
        except Exception as exc:
            log.warning(
                "GovernanceHealthAggregator: routing health collection failed: %s; defaulting to 1.0",
                exc,
            )
            return 1.0

    def _collect_admission_rate(self) -> float:
        """Phase 26: Collect admission rate signal from AdmissionRateTracker.

        Default is 1.0 (full contribution) when no tracker is wired — no
        penalisation for deployments that have not yet wired admission tracking.
        """
        if self._admission_tracker is None:
            return 1.0
        try:
            return float(max(0.0, min(1.0, self._admission_tracker.admission_rate_score())))
        except Exception as exc:
            log.warning(
                "GovernanceHealthAggregator: admission rate collection failed: %s; defaulting to 1.0",
                exc,
            )
            return 1.0

    def _collect_debt_health(self) -> float:
        """Phase 32: Collect governance debt health signal from GovernanceDebtLedger.

        Normalises ``compound_debt_score`` into a ``[0.0, 1.0]`` health value:

            debt_health = max(0.0, 1.0 - compound_debt_score / breach_threshold)

        - ``compound_debt_score == 0`` → ``1.0`` (pristine, no warnings)
        - ``compound_debt_score >= breach_threshold`` → ``0.0`` (fully breached)

        Default is ``1.0`` (fail-safe) when:
        - No ledger is wired (single-node, debt tracking not yet active)
        - Ledger has no snapshot yet (no epochs run through debt accumulation)
        - ``breach_threshold <= 0`` (misconfiguration guard — treated as pristine)
        """
        if self._debt_ledger is None:
            return 1.0
        try:
            snap = self._debt_ledger.last_snapshot
            if snap is None:
                return 1.0
            breach_threshold = float(snap.breach_threshold)
            if breach_threshold <= 0.0:
                return 1.0
            compound = float(snap.compound_debt_score)
            score = max(0.0, 1.0 - compound / breach_threshold)
            return round(min(1.0, max(0.0, score)), 6)
        except Exception as exc:
            log.warning(
                "GovernanceHealthAggregator: debt health collection failed: %s; defaulting to 1.0",
                exc,
            )
            return 1.0

    def _collect_certifier_health(self) -> float:
        """Phase 33: Collect certifier rejection rate from CertifierScanReader.

        Normalises the rejection rate into a ``[0.0, 1.0]`` health value:

            certifier_health = 1.0 - rejection_rate

        - ``rejection_rate == 0.0`` → ``1.0`` (all scans certified, pristine)
        - ``rejection_rate == 1.0`` → ``0.0`` (all scans rejected, fully degraded)

        Default is ``1.0`` (fail-safe) when:
        - No reader is wired (certifier scanning not yet active)
        - Empty scan history (no scans recorded → no evidence of rejection)
        - Any exception during collection
        """
        if self._certifier_reader is None:
            return 1.0
        try:
            rejection_rate = self._certifier_reader.rejection_rate()
            return round(min(1.0, max(0.0, 1.0 - float(rejection_rate))), 6)
        except Exception as exc:
            log.warning(
                "GovernanceHealthAggregator: certifier health collection failed: %s; defaulting to 1.0",
                exc,
            )
            return 1.0

    def _collect_gate_approval_health(self) -> float:
        """Phase 35: Collect gate decision approval rate from GateDecisionReader.

        Score = ``approval_rate`` (fraction of GateDecision outcomes approved):

            gate_health = approval_rate

        - ``approval_rate == 1.0`` → ``1.0`` (all mutations approved, pristine)
        - ``approval_rate == 0.0`` → ``0.0`` (all mutations denied, fully degraded)

        Default is ``1.0`` (fail-safe) when:
        - No reader is wired (gate decision ledger not yet active)
        - Empty decision history (no decisions recorded → no evidence of denial)
        - Any exception during collection
        """
        if self._gate_decision_reader is None:
            return 1.0
        try:
            approval_rate = self._gate_decision_reader.approval_rate()
            return round(min(1.0, max(0.0, float(approval_rate))), 6)
        except Exception as exc:
            log.warning(
                "GovernanceHealthAggregator: gate approval health collection failed: %s; defaulting to 1.0",
                exc,
            )
            return 1.0


    # ------------------------------------------------------------------
    # Math
    # ------------------------------------------------------------------

    @staticmethod
    def _weighted_sum(breakdown: Dict[str, float]) -> float:
        total = 0.0
        for signal_id, weight in SIGNAL_WEIGHTS.items():
            value = breakdown.get(signal_id, 0.0)
            total += weight * min(1.0, max(0.0, value))
        return round(min(1.0, max(0.0, total)), 6)

    # ------------------------------------------------------------------
    # Weight validation & digest
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_weights(weights: Dict[str, float]) -> None:
        weight_sum = sum(weights.values())
        if abs(weight_sum - 1.0) > _WEIGHT_SUM_TOLERANCE:
            raise ValueError(
                f"GovernanceHealthAggregator: weights must sum to 1.0; got {weight_sum}"
            )
        for k, v in weights.items():
            if not (0.0 < v < 1.0):
                raise ValueError(
                    f"GovernanceHealthAggregator: weight for '{k}' must be in (0, 1); got {v}"
                )

    @staticmethod
    def _digest_weights(weights: Dict[str, float]) -> str:
        canonical = json.dumps(
            {k: weights[k] for k in sorted(weights)}, separators=(",", ":")
        ).encode()
        return "sha256:" + hashlib.sha256(canonical).hexdigest()

    # ------------------------------------------------------------------
    # Journal emission
    # ------------------------------------------------------------------

    def _emit_snapshot(self, snapshot: HealthSnapshot) -> None:
        try:
            self._journal_emit(
                JOURNAL_EVENT_SNAPSHOT,
                {
                    "epoch_id":                  snapshot.epoch_id,
                    "health_score":              snapshot.health_score,
                    "signal_breakdown":          snapshot.signal_breakdown,
                    "weight_snapshot_digest":    snapshot.weight_snapshot_digest,
                    "constitution_version":      snapshot.constitution_version,
                    "scoring_algorithm_version": snapshot.scoring_algorithm_version,
                    "degraded":                  snapshot.degraded,
                },
            )
        except Exception as exc:  # pragma: no cover
            log.warning("GovernanceHealthAggregator: snapshot journal emit failed: %s", exc)

    def _emit_degraded(self, snapshot: HealthSnapshot) -> None:
        try:
            self._journal_emit(
                JOURNAL_EVENT_DEGRADED,
                {
                    "epoch_id":        snapshot.epoch_id,
                    "health_score":    snapshot.health_score,
                    "signal_breakdown": snapshot.signal_breakdown,
                    "threshold":       HEALTH_DEGRADED_THRESHOLD,
                },
            )
        except Exception as exc:  # pragma: no cover
            log.warning("GovernanceHealthAggregator: degraded journal emit failed: %s", exc)

    # ------------------------------------------------------------------
    # Default journal emit
    # ------------------------------------------------------------------

    @staticmethod
    def _default_journal_emit(event_type: str, payload: Dict[str, Any]) -> None:
        try:
            from security.ledger.journal import append_tx
            append_tx(event_type, payload)
        except Exception as exc:  # pragma: no cover
            log.warning("GovernanceHealthAggregator: default journal emit: %s", exc)
