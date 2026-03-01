# SPDX-License-Identifier: Apache-2.0
"""
Deterministic mutation scaffolding and scoring helpers.

Senior-grade enhancements in this revision:
- horizon_roi is normalized to [0,1] before weighting. Prior version could
  produce unbounded positive values when strategic_horizon approaches zero,
  inflating composite scores past 1.0 and bypassing acceptance thresholds.
- Hard floor/ceiling clamp [0.0, 1.0] applied after composite computation.
  No mutation can score outside this range regardless of extreme inputs.
- Out-of-range input warnings surfaced in MutationScore for governance audit.
- Dimension breakdown returned for full scoring transparency.
- Weight constants declared at module level for auditability and override.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# -- Constants ----------------------------------------------------------------

# Composite weights. Must sum to 1.0 for gain terms (penalties are subtractive).
COMPOSITE_WEIGHTS: Dict[str, float] = {
    "expected_gain":     0.35,
    "coverage_delta":    0.25,
    "horizon_roi":       0.20,
    "risk_penalty":      0.20,   # applied negated
    "complexity_penalty": 0.10,  # applied negated
}

DEFAULT_ACCEPTANCE_THRESHOLD: float = 0.25
HARD_FLOOR:    float = 0.0
HARD_CEILING:  float = 1.0


# -- Dataclasses --------------------------------------------------------------


@dataclass(frozen=True)
class MutationCandidate:
    mutation_id: str
    expected_gain: float
    risk_score: float
    complexity: float
    coverage_delta: float
    strategic_horizon: float = 1.0
    forecast_roi: float = 0.0
    # Optional per-candidate weight override. When provided, overrides
    # COMPOSITE_WEIGHTS for this candidate only.
    weight_override: Optional[Dict[str, float]] = None


@dataclass(frozen=True)
class MutationScore:
    mutation_id: str
    score: float
    accepted: bool
    dimension_breakdown: Optional[Dict[str, float]] = None
    warnings: Optional[List[str]] = None


# -- Scoring ------------------------------------------------------------------


def score_candidate(
    candidate: MutationCandidate,
    acceptance_threshold: float = DEFAULT_ACCEPTANCE_THRESHOLD,
) -> MutationScore:
    """
    Compute a deterministic, bounded composite mutation score.

    Returns a MutationScore with:
    - score in [0.0, 1.0] (hard-clamped, never out of range)
    - accepted=True only when score >= threshold AND no hard input violations
    - dimension_breakdown for audit/observability
    - warnings for any out-of-range inputs (flags, does not auto-reject)
    """
    warnings: List[str] = []
    weights = candidate.weight_override or COMPOSITE_WEIGHTS

    # Normalize forecast_roi to [0, 1] relative to strategic horizon.
    # Without this clamp, a near-zero horizon with any positive ROI produces
    # a massive multiplier that can push composite far above 1.0.
    horizon_factor = max(0.10, float(candidate.strategic_horizon))
    horizon_roi_raw = float(candidate.forecast_roi) / horizon_factor
    if horizon_roi_raw > 1.0:
        warnings.append(f"horizon_roi_clamped:{horizon_roi_raw:.4f}->1.0")
    horizon_roi = min(1.0, max(0.0, horizon_roi_raw))

    # Input range warnings -- flag for governance, do not auto-reject.
    if not (0.0 <= candidate.expected_gain <= 1.0):
        warnings.append(f"expected_gain_out_of_range:{candidate.expected_gain}")
    if not (0.0 <= candidate.risk_score <= 1.0):
        warnings.append(f"risk_score_out_of_range:{candidate.risk_score}")
    if not (0.0 <= candidate.complexity <= 1.0):
        warnings.append(f"complexity_out_of_range:{candidate.complexity}")
    if not (0.0 <= candidate.coverage_delta <= 1.0):
        warnings.append(f"coverage_delta_out_of_range:{candidate.coverage_delta}")

    # Dimension contributions.
    eg_contrib   = float(candidate.expected_gain) * weights.get("expected_gain", 0.35)
    cd_contrib   = float(candidate.coverage_delta) * weights.get("coverage_delta", 0.25)
    hr_contrib   = horizon_roi * weights.get("horizon_roi", 0.20)
    risk_pen     = float(candidate.risk_score) * weights.get("risk_penalty", 0.20)
    complex_pen  = float(candidate.complexity) * weights.get("complexity_penalty", 0.10)

    raw = eg_contrib + cd_contrib + hr_contrib - risk_pen - complex_pen
    score = round(min(HARD_CEILING, max(HARD_FLOOR, raw)), 4)

    breakdown: Dict[str, float] = {
        "expected_gain_contrib":      round(eg_contrib, 4),
        "coverage_delta_contrib":     round(cd_contrib, 4),
        "horizon_roi_contrib":        round(hr_contrib, 4),
        "risk_penalty_contrib":       round(-risk_pen, 4),
        "complexity_penalty_contrib": round(-complex_pen, 4),
        "raw_before_clamp":           round(raw, 4),
    }

    # Hard input violations downgrade acceptance regardless of threshold.
    has_hard_violation = any("_out_of_range" in w for w in warnings)
    accepted = (score >= acceptance_threshold) and not has_hard_violation

    return MutationScore(
        mutation_id=candidate.mutation_id,
        score=score,
        accepted=accepted,
        dimension_breakdown=breakdown,
        warnings=warnings if warnings else None,
    )


def rank_mutation_candidates(
    candidates: list[MutationCandidate],
    acceptance_threshold: float = DEFAULT_ACCEPTANCE_THRESHOLD,
) -> list[MutationScore]:
    scores = [
        score_candidate(c, acceptance_threshold=acceptance_threshold)
        for c in candidates
    ]
    return sorted(scores, key=lambda item: (-item.score, item.mutation_id))
