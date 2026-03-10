# SPDX-License-Identifier: Apache-2.0
"""Runtime facade exposing orchestrator-safe runtime services."""

from typing import Any, Iterable

from security.ledger import journal
from runtime.governance.review_pressure import (
    HIGH_REPUTATION_THRESHOLD,
    compute_tier_reviewer_count,
)
from runtime.governance.reviewer_reputation import (
    SCORING_ALGORITHM_VERSION,
    compute_epoch_reputation_batch,
)

from runtime import metrics
from runtime.boot import BootPreflightService
from runtime.boot.preflight import evaluate_boot_invariants
from runtime.capability_graph import register_capability
from runtime.constitution import (
    CONSTITUTION_VERSION,
    determine_tier,
    deterministic_envelope_scope,
    get_forced_tier,
)
from runtime.element_registry import dump, register
from runtime.evolution import EvolutionRuntime
from runtime.evolution.checkpoint_verifier import CheckpointVerificationError, CheckpointVerifier
from runtime.evolution.lineage_v2 import LineageIntegrityError
from runtime.evolution.replay_attestation import ReplayProofBuilder
from runtime.evolution.replay_mode import ReplayMode, normalize_replay_mode
from runtime.evolution.replay_service import ReplayVerificationService
from runtime.fitness_v2 import score_mutation_enhanced
from runtime.founders_law import (
    RULE_ARCHITECT_SCAN,
    RULE_CONSTITUTION_VERSION,
    RULE_KEY_ROTATION,
    RULE_LEDGER_INTEGRITY,
    RULE_MUTATION_ENGINE,
    RULE_PLATFORM_RESOURCES,
    RULE_WARM_POOL,
    enforce_law,
)
from runtime.governance.foundation import default_provider
from runtime.governance.decision_pipeline import evaluate_mutation_decision as evaluate_mutation
from runtime.preflight import validate_constitution_version_config
from runtime.manifest.generator import generate_tool_manifest
from runtime.mcp.server import create_app as create_mcp_app
from runtime.platform.android_monitor import AndroidMonitor
from runtime.platform.storage_manager import StorageManager
from runtime.recovery.ledger_guardian import AutoRecoveryHook, SnapshotManager
from runtime.recovery.tier_manager import RecoveryPolicy, RecoveryTierLevel, TierManager
from runtime.timeutils import now_iso
from runtime.warm_pool import WarmPool


def reviewer_calibration_service(*, epoch_id: str, reviewer_ids: Iterable[str] | None = None) -> dict[str, Any]:
    """Aggregate reviewer calibration telemetry for the requested epoch.

    Read-only: this function only reads from ledger-backed journal events.
    """
    events = journal.read_entries(limit=5_000)
    normalized_reviewer_ids = [rid.strip() for rid in (reviewer_ids or []) if rid and rid.strip()]

    if not normalized_reviewer_ids:
        inferred: set[str] = set()
        for entry in events:
            payload = entry.get("payload") if isinstance(entry, dict) else {}
            if isinstance(payload, dict) and str(payload.get("epoch_id") or "") == epoch_id:
                reviewer_id = str(payload.get("reviewer_id") or "").strip()
                if reviewer_id:
                    inferred.add(reviewer_id)
        normalized_reviewer_ids = sorted(inferred)

    reputation_scores = compute_epoch_reputation_batch(
        normalized_reviewer_ids,
        events,
        epoch_id=epoch_id,
        scoring_algorithm_version=SCORING_ALGORITHM_VERSION,
    )

    composite_scores = [record["composite_score"] for record in reputation_scores.values()]
    avg_reputation = round(sum(composite_scores) / len(composite_scores), 6) if composite_scores else 0.0

    cohort_summary = {
        "high": sum(1 for score in composite_scores if score >= HIGH_REPUTATION_THRESHOLD),
        "standard": sum(1 for score in composite_scores if 0.60 <= score < HIGH_REPUTATION_THRESHOLD),
        "low": sum(1 for score in composite_scores if score < 0.60),
    }

    calibration = compute_tier_reviewer_count("standard", avg_reputation)
    if calibration["adjustment"] < 0:
        tier_pressure = "extended"
    elif calibration["adjustment"] > 0:
        tier_pressure = "elevated"
    else:
        tier_pressure = "nominal"

    return {
        "cohort_summary": cohort_summary,
        "avg_reputation": avg_reputation,
        "tier_pressure": tier_pressure,
        "constitutional_floor": "enforced",
        "epoch_id": epoch_id,
        "constitution_version": CONSTITUTION_VERSION,
        "scoring_algorithm_version": SCORING_ALGORITHM_VERSION,
    }

__all__ = [
    "AutoRecoveryHook",
    "AndroidMonitor",
    "BootPreflightService",
    "CONSTITUTION_VERSION",
    "CheckpointVerificationError",
    "CheckpointVerifier",
    "EvolutionRuntime",
    "LineageIntegrityError",
    "RULE_ARCHITECT_SCAN",
    "RULE_CONSTITUTION_VERSION",
    "RULE_KEY_ROTATION",
    "RULE_LEDGER_INTEGRITY",
    "RULE_MUTATION_ENGINE",
    "RULE_PLATFORM_RESOURCES",
    "RULE_WARM_POOL",
    "RecoveryPolicy",
    "RecoveryTierLevel",
    "ReplayMode",
    "ReplayProofBuilder",
    "ReplayVerificationService",
    "SnapshotManager",
    "StorageManager",
    "TierManager",
    "WarmPool",
    "create_mcp_app",
    "default_provider",
    "determine_tier",
    "deterministic_envelope_scope",
    "dump",
    "enforce_law",
    "evaluate_mutation",
    "evaluate_boot_invariants",
    "generate_tool_manifest",
    "get_forced_tier",
    "metrics",
    "normalize_replay_mode",
    "now_iso",
    "register",
    "register_capability",
    "reviewer_calibration_service",
    "score_mutation_enhanced",
    "validate_constitution_version_config",
]


def governance_health_service(*, epoch_id: str) -> dict[str, Any]:
    """Compute governance health snapshot for the requested epoch.

    Returns a dict suitable for direct JSON serialisation in the
    ``GET /governance/health`` endpoint.  Read-only; no mutation authority.
    """
    from runtime.governance.health_aggregator import (
        HEALTH_DEGRADED_THRESHOLD,
        GovernanceHealthAggregator,
    )

    # Wire Phase 5–7 dependencies from the active runtime (best-effort).
    # Any missing dependency degrades gracefully per GovernanceHealthAggregator.
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

    # Phase 23: wire routing analytics engine (best-effort, from active telemetry sink)
    routing_analytics_engine = None
    try:
        from server import _telemetry_sink_ref
        from runtime.intelligence.file_telemetry_sink import FileTelemetrySink, TelemetryLedgerReader
        from runtime.intelligence.strategy_analytics import StrategyAnalyticsEngine
        if isinstance(_telemetry_sink_ref, FileTelemetrySink):
            reader = TelemetryLedgerReader(_telemetry_sink_ref._path)
            routing_analytics_engine = StrategyAnalyticsEngine(reader)
    except Exception:
        pass

    agg = GovernanceHealthAggregator(
        reviewer_reputation_ledger=reviewer_reputation_ledger,
        roadmap_amendment_engine=amendment_engine,
        federated_evidence_matrix=evidence_matrix,
        epoch_telemetry=epoch_telemetry,
        routing_analytics_engine=routing_analytics_engine,
    )

    snapshot = agg.compute(epoch_id)

    h = snapshot.health_score
    if h >= 0.80:
        status = "green"
    elif h >= HEALTH_DEGRADED_THRESHOLD:
        status = "amber"
    else:
        status = "red"

    # Phase 23: routing_health summary field
    routing_health_summary: dict[str, Any] = {"available": False, "status": "green",
                                               "health_score": 1.0, "dominant_strategy": None,
                                               "report_digest": None, "analytics_version": "22.0"}
    if snapshot.routing_health_report is not None:
        routing_health_summary = {
            "available": snapshot.routing_health_report.get("available", True),
            "status": snapshot.routing_health_report.get("status", "green"),
            "health_score": snapshot.routing_health_report.get("health_score", 1.0),
            "dominant_strategy": snapshot.routing_health_report.get("dominant_strategy"),
            "report_digest": snapshot.routing_health_report.get("report_digest"),
            "analytics_version": "22.0",
        }

    return {
        "epoch_id":                  snapshot.epoch_id,
        "health_score":              snapshot.health_score,
        "status":                    status,
        "signal_breakdown":          snapshot.signal_breakdown,
        "weight_snapshot_digest":    snapshot.weight_snapshot_digest,
        "constitution_version":      snapshot.constitution_version,
        "scoring_algorithm_version": snapshot.scoring_algorithm_version,
        "degraded":                  snapshot.degraded,
        "routing_health":            routing_health_summary,  # Phase 23
    }
