# SPDX-License-Identifier: Apache-2.0
"""
CritiqueModule: governed five-dimension mutation review.

Senior-grade rewrite addressing the single most dangerous governance bypass
in the v1.0.0 codebase: the auto-pass guard that approved every proposal
with estimated_impact >= 0.0 (which is always true for valid proposals).

Changes in this revision:
- Auto-pass guard deleted entirely. Approval now requires composite >= 0.60
  AND all five dimension floors to pass.
- Five independent scoring dimensions with individual floor thresholds.
- Risk dimension is inverted in composite: high raw risk score -> low contribution.
- Fail-closed on any single floor breach regardless of composite.
- Deterministic review digest for lineage/audit traceability.
- All dimension scores and verdicts surfaced in CritiqueResult for observability.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping

from runtime.intelligence.proposal import Proposal

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

# Floor thresholds per dimension.
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

    Approval requires:
      1. Composite weighted score >= APPROVAL_THRESHOLD (0.60)
      2. Every dimension's effective score >= its configured floor (fail-closed)

    The prior auto-pass guard (estimated_impact >= 0.0 -> approved) is removed.
    estimated_impact >= 0.0 is unconditionally true for any valid Proposal and
    rendered the entire critique pipeline a governance no-op.
    """

    def review(self, proposal: Proposal) -> CritiqueResult:
        dims = self._score_all_dimensions(proposal)
        composite = self._composite(dims)
        risk_flags = self._check_dimension_floors(dims)
        verdicts = self._verdicts(dims)

        approved = (composite >= APPROVAL_THRESHOLD) and (len(risk_flags) == 0)
        notes = self._build_notes(composite, risk_flags, approved)
        digest = self._review_digest(proposal, dims, composite)

        log.info(
            "critique.review proposal=%s composite=%.3f approved=%s flags=%s",
            proposal.proposal_id,
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
            metadata={"proposal_id": proposal.proposal_id, "algorithm_version": "v2.0.0"},
            dimension_verdicts=verdicts,
            risk_flags=risk_flags,
            review_digest=digest,
            algorithm_version="v2.0.0",
        )

    # -- Dimension scorers ----------------------------------------------------
    # Each returns [0.0, 1.0]. "risk" is 0=safe, 1=max risk (inverted in composite).

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

    def _check_dimension_floors(self, dims: Dict[str, float]) -> List[str]:
        flags: List[str] = []
        for dim, floor in DIMENSION_FLOORS.items():
            raw = dims.get(dim, 0.0)
            effective = (1.0 - raw) if dim == "risk" else raw
            if effective < floor:
                flags.append(f"{dim}_below_floor:effective={effective:.3f}<floor={floor}")
        return flags

    def _verdicts(self, dims: Dict[str, float]) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for dim, floor in DIMENSION_FLOORS.items():
            raw = dims.get(dim, 0.0)
            effective = (1.0 - raw) if dim == "risk" else raw
            out[dim] = "pass" if effective >= floor else "fail"
        return out

    def _build_notes(self, composite: float, risk_flags: List[str], approved: bool) -> str:
        if approved:
            return f"approved: composite={composite:.3f} >= threshold={APPROVAL_THRESHOLD}"
        if risk_flags:
            return f"rejected: floor_breach -- {'; '.join(risk_flags)}"
        return f"rejected: composite={composite:.3f} < threshold={APPROVAL_THRESHOLD}"

    def _review_digest(
        self, proposal: Proposal, dims: Dict[str, float], composite: float
    ) -> str:
        payload = json.dumps(
            {
                "proposal_id": proposal.proposal_id,
                "dims": {k: round(v, 6) for k, v in sorted(dims.items())},
                "composite": round(composite, 6),
                "algorithm_version": "v2.0.0",
            },
            sort_keys=True,
        ).encode()
        return "sha256:" + hashlib.sha256(payload).hexdigest()
