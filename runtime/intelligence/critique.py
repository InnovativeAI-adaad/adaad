# SPDX-License-Identifier: Apache-2.0
"""
CritiqueModule: governed five-dimension mutation review.

Phase 16: Per-strategy dimension floor overrides. Each of the six STRATEGY_TAXONOMY
strategies can raise (never lower) dimension floors to match its risk profile.
Overrides are additive upper-only adjustments to the baseline DIMENSION_FLOORS.

Original invariants preserved:
- Auto-pass guard remains deleted.
- Approval requires composite >= APPROVAL_THRESHOLD AND all dimension floors pass.
- Risk dimension is inverted in composite.
- Fail-closed on any single floor breach.
- review_digest covers strategy_id for determinism tracing.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from runtime.intelligence.proposal import Proposal
from runtime.intelligence.strategy import STRATEGY_TAXONOMY

log = logging.getLogger(__name__)

CRITIQUE_DIMENSIONS = (
    "risk",
    "alignment",
    "feasibility",
    "governance",
    "observability",
)

# -- Scoring constants --------------------------------------------------------

APPROVAL_THRESHOLD: float = 0.60

# Baseline floor thresholds per dimension.
# For "risk", floor applies to the *inverted* value (1 - raw_risk).
DIMENSION_FLOORS: Dict[str, float] = {
    "risk":          0.30,
    "alignment":     0.40,
    "feasibility":   0.35,
    "governance":    0.50,
    "observability": 0.20,
}

# Composite weights -- must sum to 1.0.
DIMENSION_WEIGHTS: Dict[str, float] = {
    "risk":          0.30,
    "alignment":     0.25,
    "feasibility":   0.20,
    "governance":    0.15,
    "observability": 0.10,
}

# Phase 16: Per-strategy floor OVERRIDES.
# Values MUST be >= baseline DIMENSION_FLOORS — floors may only be raised.
# Missing dimensions fall back to the baseline floor.
STRATEGY_FLOOR_OVERRIDES: Dict[str, Dict[str, float]] = {
    "adaptive_self_mutate": {
        # Standard aggressiveness — no overrides needed beyond baseline.
    },
    "conservative_hold": {
        "risk":          0.55,  # Tighter risk floor: low-risk only
        "governance":    0.65,  # Stronger governance requirement
    },
    "structural_refactor": {
        "feasibility":   0.50,  # Refactors must be concretely feasible
        "observability": 0.35,  # Must include traceability evidence
    },
    "test_coverage_expansion": {
        "observability": 0.40,  # Tests must surface observable evidence
        "governance":    0.60,  # Coverage PRs need strong governance
    },
    "performance_optimization": {
        "risk":          0.45,  # Perf changes carry higher risk floor
        "feasibility":   0.45,  # Must demonstrate concrete path
    },
    "safety_hardening": {
        "risk":          0.65,  # Hardening must pass strict risk floor
        "governance":    0.70,  # Highest governance requirement of all strategies
        "observability": 0.45,  # Evidence of hardening must be observable
    },
}


def _effective_floors(strategy_id: Optional[str]) -> Dict[str, float]:
    """Return dimension floors for the given strategy_id.

    Floors are the maximum of baseline and any override — never lowered.
    Unknown or None strategy_id returns baseline floors unchanged.
    """
    overrides = STRATEGY_FLOOR_OVERRIDES.get(strategy_id or "", {}) if strategy_id else {}
    return {
        dim: max(DIMENSION_FLOORS[dim], overrides.get(dim, 0.0))
        for dim in DIMENSION_FLOORS
    }


_GOVERNANCE_FIELDS = ("proposal_id", "title", "summary", "evidence")
_OBSERVABILITY_KEYS = ("traces", "metrics", "logs", "test_ids", "replay_digest")


# -- Result dataclass ---------------------------------------------------------


@dataclass(frozen=True)
class CritiqueResult:
    approved: bool
    per_dimension_scores: Mapping[str, float]
    weighted_aggregate: float
    risk_score: float
    notes: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    dimension_verdicts: Mapping[str, str] = field(default_factory=dict)
    risk_flags: List[str] = field(default_factory=list)
    review_digest: str = ""
    algorithm_version: str = "v2.0.0"


# -- CritiqueModule -----------------------------------------------------------


class CritiqueModule:
    """
    Five-dimension deterministic critique gate for mutation proposals.

    Phase 16: accepts optional strategy_id to apply per-strategy floor overrides.
    Floors may only be raised — never lowered below baseline DIMENSION_FLOORS.

    Approval requires:
      1. Composite weighted score >= APPROVAL_THRESHOLD (0.60)
      2. Every dimension's effective score >= its strategy-adjusted floor (fail-closed)
    """

    def review(
        self,
        proposal: Proposal,
        *,
        strategy_id: Optional[str] = None,
    ) -> CritiqueResult:
        """Review a mutation proposal.

        Args:
            proposal: The mutation proposal to evaluate.
            strategy_id: Optional STRATEGY_TAXONOMY member. When provided, applies
                         per-strategy dimension floor overrides. Unknown strategy_ids
                         are silently ignored (defensive; floors fall back to baseline).
        """
        # Validate strategy_id if provided — defensive only, no exception on unknown
        effective_strategy = strategy_id if strategy_id in STRATEGY_TAXONOMY else None
        floors = _effective_floors(effective_strategy)

        dims = self._score_all_dimensions(proposal)
        composite = self._composite(dims)
        risk_flags = self._check_dimension_floors(dims, floors)
        verdicts = self._verdicts(dims, floors)

        approved = (composite >= APPROVAL_THRESHOLD) and (len(risk_flags) == 0)
        notes = self._build_notes(composite, risk_flags, approved)
        digest = self._review_digest(proposal, dims, composite, effective_strategy)

        log.info(
            "critique.review proposal=%s strategy=%s composite=%.3f approved=%s flags=%s",
            proposal.proposal_id,
            effective_strategy or "baseline",
            composite,
            approved,
            risk_flags,
        )

        return CritiqueResult(
            approved=approved,
            per_dimension_scores={k: round(v, 4) for k, v in dims.items()},
            weighted_aggregate=round(composite, 4),
            risk_score=round(dims["risk"], 4),
            notes=notes,
            metadata={
                "proposal_id": proposal.proposal_id,
                "algorithm_version": "v2.0.0",
                "strategy_id": effective_strategy or "baseline",
                "critique_taxonomy_version": "16.0",
            },
            dimension_verdicts=verdicts,
            risk_flags=risk_flags,
            review_digest=digest,
            algorithm_version="v2.0.0",
        )

    # -- Dimension scorers (unchanged from v2.0.0) ----------------------------

    def _score_risk(self, proposal: Proposal) -> float:
        impact = float(getattr(proposal, "estimated_impact", 0.0) or 0.0)
        impact_risk = min(1.0, abs(impact) / 2.0)
        diff_absent_penalty = 0.20 if not getattr(proposal, "real_diff", "") else 0.0
        evidence = getattr(proposal, "evidence", {}) or {}
        evidence_gap = 0.15 if not evidence else 0.0
        return min(1.0, impact_risk + diff_absent_penalty + evidence_gap)

    def _score_alignment(self, proposal: Proposal) -> float:
        score = 0.0
        title = (getattr(proposal, "title", "") or "").strip()
        summary = (getattr(proposal, "summary", "") or "").strip()
        projected = getattr(proposal, "projected_impact", {}) or {}
        if title and len(title) >= 10:
            score += 0.35
        if summary and len(summary) >= 20:
            score += 0.40
        if projected:
            score += 0.25
        return min(1.0, score)

    def _score_feasibility(self, proposal: Proposal) -> float:
        score = 0.30
        real_diff = (getattr(proposal, "real_diff", "") or "").strip()
        target_files = getattr(proposal, "target_files", ()) or ()
        if real_diff:
            score += min(0.40, 0.10 + (real_diff.count("\n") + 1) / 200.0)
        if target_files:
            score += min(0.30, len(target_files) * 0.08)
        return min(1.0, score)

    def _score_governance(self, proposal: Proposal) -> float:
        present = sum(1 for f in _GOVERNANCE_FIELDS if getattr(proposal, f, None))
        base = present / len(_GOVERNANCE_FIELDS)
        pid = getattr(proposal, "proposal_id", "") or ""
        slug_bonus = 0.10 if (":" in pid and len(pid) >= 5) else 0.0
        return min(1.0, base + slug_bonus)

    def _score_observability(self, proposal: Proposal) -> float:
        evidence = getattr(proposal, "evidence", {}) or {}
        if not isinstance(evidence, dict):
            return 0.10
        hits = sum(1 for k in _OBSERVABILITY_KEYS if k in evidence)
        return min(1.0, 0.20 + (hits / len(_OBSERVABILITY_KEYS)) * 0.80)

    # -- Composite + helpers --------------------------------------------------

    def _score_all_dimensions(self, proposal: Proposal) -> Dict[str, float]:
        return {
            "risk":          self._score_risk(proposal),
            "alignment":     self._score_alignment(proposal),
            "feasibility":   self._score_feasibility(proposal),
            "governance":    self._score_governance(proposal),
            "observability": self._score_observability(proposal),
        }

    def _composite(self, dims: Dict[str, float]) -> float:
        total = 0.0
        for dim, weight in DIMENSION_WEIGHTS.items():
            raw = dims.get(dim, 0.0)
            contribution = (1.0 - raw) if dim == "risk" else raw
            total += weight * contribution
        return min(1.0, max(0.0, total))

    def _check_dimension_floors(
        self, dims: Dict[str, float], floors: Dict[str, float]
    ) -> List[str]:
        flags: List[str] = []
        for dim, floor in floors.items():
            raw = dims.get(dim, 0.0)
            effective = (1.0 - raw) if dim == "risk" else raw
            if effective < floor:
                flags.append(f"{dim}_below_floor:effective={effective:.3f}<floor={floor}")
        return flags

    def _verdicts(
        self, dims: Dict[str, float], floors: Dict[str, float]
    ) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for dim, floor in floors.items():
            raw = dims.get(dim, 0.0)
            effective = (1.0 - raw) if dim == "risk" else raw
            out[dim] = "pass" if effective >= floor else "fail"
        return out

    def _build_notes(
        self, composite: float, risk_flags: List[str], approved: bool
    ) -> str:
        if approved:
            return f"approved: composite={composite:.3f} >= threshold={APPROVAL_THRESHOLD}"
        if risk_flags:
            return f"rejected: floor_breach -- {'; '.join(risk_flags)}"
        return f"rejected: composite={composite:.3f} < threshold={APPROVAL_THRESHOLD}"

    def _review_digest(
        self,
        proposal: Proposal,
        dims: Dict[str, float],
        composite: float,
        strategy_id: Optional[str],
    ) -> str:
        payload = json.dumps(
            {
                "proposal_id": proposal.proposal_id,
                "dims": {k: round(v, 6) for k, v in sorted(dims.items())},
                "composite": round(composite, 6),
                "strategy_id": strategy_id or "baseline",
                "algorithm_version": "v2.0.0",
            },
            sort_keys=True,
        ).encode()
        return "sha256:" + hashlib.sha256(payload).hexdigest()
