# SPDX-License-Identifier: Apache-2.0
"""Governance Health Service — standalone facade for GET /governance/health.

Kept separate from runtime.api.runtime_services to avoid circular imports
with the FastAPI server layer.
"""

from __future__ import annotations

from typing import Any, Dict

from runtime.governance.health_aggregator import (
    HEALTH_DEGRADED_THRESHOLD,
    GovernanceHealthAggregator,
)


def governance_health_service(*, epoch_id: str) -> Dict[str, Any]:
    """Compute governance health snapshot for ``epoch_id``.

    Read-only. No mutation authority. All dependencies are wired best-effort;
    any missing dependency degrades the corresponding signal to its safe default.
    """
    reviewer_reputation_ledger = None
    amendment_engine = None
    evidence_matrix = None
    epoch_telemetry = None

    try:
        from runtime.governance.reviewer_reputation_ledger import ReviewerReputationLedger
        reviewer_reputation_ledger = ReviewerReputationLedger()
        reviewer_reputation_ledger.load()
    except Exception:
        pass

    try:
        from runtime.autonomy.roadmap_amendment_engine import RoadmapAmendmentEngine
        amendment_engine = RoadmapAmendmentEngine()
    except Exception:
        pass

    try:
        from runtime.governance.federation.federated_evidence_matrix import FederatedEvidenceMatrix
        evidence_matrix = FederatedEvidenceMatrix()
    except Exception:
        pass

    try:
        from runtime.autonomy.epoch_telemetry import EpochTelemetry
        epoch_telemetry = EpochTelemetry.load_from_disk()
    except Exception:
        pass

    agg = GovernanceHealthAggregator(
        reviewer_reputation_ledger=reviewer_reputation_ledger,
        roadmap_amendment_engine=amendment_engine,
        federated_evidence_matrix=evidence_matrix,
        epoch_telemetry=epoch_telemetry,
    )

    snapshot = agg.compute(epoch_id)

    h = snapshot.health_score
    if h >= 0.80:
        status = "green"
    elif h >= HEALTH_DEGRADED_THRESHOLD:
        status = "amber"
    else:
        status = "red"

    return {
        "epoch_id":                  snapshot.epoch_id,
        "health_score":              snapshot.health_score,
        "status":                    status,
        "signal_breakdown":          snapshot.signal_breakdown,
        "weight_snapshot_digest":    snapshot.weight_snapshot_digest,
        "constitution_version":      snapshot.constitution_version,
        "scoring_algorithm_version": snapshot.scoring_algorithm_version,
        "degraded":                  snapshot.degraded,
    }
