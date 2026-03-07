# SPDX-License-Identifier: Apache-2.0
"""
Impact scoring for governed mutation bundles.

Senior-grade enhancements in this revision:
- Graduated keyword tiers (CRITICAL / HIGH / MEDIUM) for structural risk.
  Prior version treated all high-risk keywords equally; touching ledger/
  certificate paths now scores 3x higher than touching a generic "core" module.
- Graduated governance_proximity: critical cryptographic paths -> 1.0,
  governance/constitution paths -> 0.70, all others -> 0.20.
  Prior binary (certificate|ledger: 1.0, else: 0.25) missed broad governance
  path families like policy/ and constitution/ subdirectories.
- Both changes preserve the existing ImpactScore API and total() property.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from runtime.api.agents import MutationRequest


@dataclass(frozen=True)
class ImpactScore:
    semantic_depth: float
    structural_risk: float
    governance_proximity: float
    lineage_divergence: float

    @property
    def total(self) -> float:
        total = (
            (self.semantic_depth * 0.35)
            + (self.structural_risk * 0.30)
            + (self.governance_proximity * 0.20)
            + (self.lineage_divergence * 0.15)
        )
        return round(min(1.0, max(0.0, total)), 3)


class ImpactScorer:
    """Compute normalized impact score for a mutation request."""

    # Graduated risk keyword tiers.
    # CRITICAL (3x weight): cryptographic / ledger infrastructure.
    # HIGH     (2x weight): governance, security, constitution.
    # MEDIUM   (1x weight): runtime, core, orchestration.
    _CRITICAL_KEYWORDS = {"ledger", "certificate", "signing_key", "event_signer", "key_rotation"}
    _HIGH_KEYWORDS     = {"security", "governance", "constitution"}
    _MEDIUM_KEYWORDS   = {"runtime", "core", "orchestrator", "mutation_engine"}

    # Deprecated set kept for backward-compat callers that may reference it.
    _HIGH_RISK_KEYWORDS = _CRITICAL_KEYWORDS | _HIGH_KEYWORDS | _MEDIUM_KEYWORDS

    _TARGET_TYPE_WEIGHTS = {
        "runtime":    1.0,
        "security":   1.0,
        "governance": 1.0,
        "code":       0.8,
        "dna":        0.3,
        "docs":       0.1,
    }

    # Governance proximity keyword tiers.
    _PROXIMITY_CRITICAL = {"ledger", "certificate", "signing_key", "key_rotation"}
    _PROXIMITY_HIGH     = {"governance", "constitution", "policy", "founders_law"}

    def score(self, request: MutationRequest) -> ImpactScore:
        targets = request.targets or []
        target_paths = [t.path.lower() for t in targets]
        target_types = [t.target_type.lower() for t in targets if t.target_type]

        ops_count = sum(len(t.ops) for t in targets) if targets else len(request.ops)
        semantic_depth = min(1.0, ops_count / 12.0)

        # Graduated structural risk.
        critical_hits = self._keyword_hits(target_paths, self._CRITICAL_KEYWORDS)
        high_hits     = self._keyword_hits(target_paths, self._HIGH_KEYWORDS)
        medium_hits   = self._keyword_hits(target_paths, self._MEDIUM_KEYWORDS)
        weighted_hits = (critical_hits * 3.0) + (high_hits * 2.0) + (medium_hits * 1.0)
        max_possible  = max(1, len(target_paths)) * 3.0
        path_risk     = min(1.0, weighted_hits / max_possible) if target_paths else 0.20
        type_risk     = max((self._TARGET_TYPE_WEIGHTS.get(t, 0.5) for t in target_types), default=0.2)
        structural_risk = min(1.0, max(path_risk, type_risk))

        # Graduated governance proximity.
        if any(kw in p for p in target_paths for kw in self._PROXIMITY_CRITICAL):
            governance_proximity = 1.0
        elif any(kw in p for p in target_paths for kw in self._PROXIMITY_HIGH):
            governance_proximity = 0.70
        else:
            governance_proximity = 0.20

        lineage_divergence = min(1.0, len({t.target_type for t in targets}) / 4.0) if targets else 0.1

        return ImpactScore(
            semantic_depth=round(semantic_depth, 3),
            structural_risk=round(structural_risk, 3),
            governance_proximity=round(governance_proximity, 3),
            lineage_divergence=round(lineage_divergence, 3),
        )

    @staticmethod
    def _keyword_hits(values: List[str], keywords: set) -> int:
        hits = 0
        for value in values:
            if any(keyword in value for keyword in keywords):
                hits += 1
        return hits


__all__ = ["ImpactScorer", "ImpactScore"]
