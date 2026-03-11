# SPDX-License-Identifier: Apache-2.0
"""
Deterministic mutation scaffolding and scoring helpers — v2.

v2 enhancements over v1:
- ScoringWeights dataclass: replaces module-level float constants with an
  externally-injectable, epoch-scoped weight bundle.  WeightAdaptor owns and
  mutates these; the scaffold is a pure consumer.
- PopulationState dataclass: GA bookkeeping (generation counter, elite roster,
  diversity pressure signal) owned by PopulationManager.
- MutationCandidate lineage extension: five Optional fields (parent_id,
  generation, agent_origin, epoch_id, source_context_hash) appended with
  keyword-only defaults — all existing positional constructors continue to work
  unchanged.
- Adaptive acceptance threshold: threshold is scaled down when diversity_pressure
  is high (exploration epochs), enabling more permissive candidate acceptance.
- Elitism bonus: +0.05 flat score bonus applied *after* threshold adjustment for
  children whose parent_id appears in PopulationState.elite_ids.
- score_candidate() / rank_mutation_candidates() remain 100% backward-compatible:
  both functions accept optional ScoringWeights and PopulationState kwargs;
  omitting them reproduces identical v1 behaviour.

Senior-grade invariants preserved from v1:
- horizon_roi normalised to [0, 1].
- Hard floor/ceiling clamp [0.0, 1.0].
- Out-of-range input warnings surfaced for governance audit.
- Full dimension breakdown returned.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional

# ---------------------------------------------------------------------------
# Module-level constants (v1 compat — still used as ScoringWeights defaults)
# ---------------------------------------------------------------------------

COMPOSITE_WEIGHTS: Dict[str, float] = {
    "expected_gain":      0.35,
    "coverage_delta":     0.25,
    "horizon_roi":        0.20,
    "risk_penalty":       0.20,
    "complexity_penalty": 0.10,
}

DEFAULT_ACCEPTANCE_THRESHOLD: float = 0.24
HARD_FLOOR:   float = 0.0
HARD_CEILING: float = 1.0

ELITISM_BONUS: float = 0.05  # flat score bonus for elite-parent children


@lru_cache(maxsize=4096)
def _stable_text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@lru_cache(maxsize=4096)
def _semantic_feature_from_digest(python_digest: str, python_content: str) -> tuple[float, float, bool]:
    if not python_content:
        return 0.0, 0.0, False
    try:
        from runtime.evolution.semantic_diff import SemanticDiffEngine as _SDE

        sdiff = _SDE().diff(before_source="", after_source=python_content)
        if not sdiff.fallback_used:
            return sdiff.risk_score, sdiff.complexity_score, True
    except Exception:  # noqa: BLE001 — graceful degradation to baseline scores
        pass
    return 0.0, 0.0, False


def _tie_break_signals(candidate: "MutationCandidate") -> tuple[float, float, float]:
    novelty = 0.0
    novelty_source = candidate.source_context_hash or candidate.mutation_id
    if novelty_source:
        novelty_digest = _stable_text_digest(novelty_source)
        novelty = int(novelty_digest[-8:], 16) / 0xFFFFFFFF

    lineage_distance = float(max(0, candidate.generation)) + (0.5 if candidate.parent_id else 0.0)
    regression_risk = (float(candidate.risk_score) * 0.7) + (float(candidate.complexity) * 0.3)
    return novelty, lineage_distance, regression_risk


# ---------------------------------------------------------------------------
# v2 Data Structures
# ---------------------------------------------------------------------------


@dataclass
class ScoringWeights:
    """
    Mutable, epoch-scoped weight bundle owned by WeightAdaptor.

    All fields are initialised to v1 COMPOSITE_WEIGHTS values so that
    score_candidate(candidate) with no extra kwargs produces the same
    result as v1 for identical inputs.
    """
    gain_weight:          float = 0.35
    coverage_weight:      float = 0.25
    horizon_weight:       float = 0.20
    risk_penalty:         float = 0.20   # static in v1 — Phase 2 extension point
    complexity_penalty:   float = 0.10   # static in v1 — Phase 2 extension point
    acceptance_threshold: float = DEFAULT_ACCEPTANCE_THRESHOLD

    def as_composite_dict(self) -> Dict[str, float]:
        """Convert to the legacy COMPOSITE_WEIGHTS key schema."""
        return {
            "expected_gain":      self.gain_weight,
            "coverage_delta":     self.coverage_weight,
            "horizon_roi":        self.horizon_weight,
            "risk_penalty":       self.risk_penalty,
            "complexity_penalty": self.complexity_penalty,
        }


@dataclass
class PopulationState:
    """
    GA bookkeeping for a single epoch, owned by PopulationManager.

    diversity_pressure in [0.0, 1.0]:
      0.0 = pure exploitation (threshold unchanged)
      1.0 = pure exploration  (threshold scaled down by 40%)
    """
    generation:         int       = 0
    elite_ids:          List[str] = field(default_factory=list)
    diversity_pressure: float     = 0.0
    _max_elite:         int       = field(default=5, repr=False)

    def advance_generation(self) -> None:
        """Increment generation counter in-place."""
        self.generation += 1

    def record_elite(self, mutation_id: str) -> None:
        """Add mutation_id to elite roster, capped at _max_elite."""
        if mutation_id not in self.elite_ids:
            self.elite_ids.append(mutation_id)
        if len(self.elite_ids) > self._max_elite:
            self.elite_ids = self.elite_ids[-self._max_elite:]


# ---------------------------------------------------------------------------
# Core Dataclasses (v2 — backward-compatible)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MutationCandidate:
    """
    Immutable mutation proposal.

    v1 positional fields (mutation_id, expected_gain, risk_score, complexity,
    coverage_delta) are unchanged.  All v2 lineage fields are keyword-only with
    safe defaults — existing test constructors continue to work without change.
    """
    # v1 fields — positional
    mutation_id:       str
    expected_gain:     float
    risk_score:        float
    complexity:        float
    coverage_delta:    float
    # v1 optional fields
    strategic_horizon: float                    = 1.0
    forecast_roi:      float                    = 0.0
    weight_override:   Optional[Dict[str, float]] = None
    # v2 lineage fields — keyword, optional
    parent_id:             Optional[str] = None
    generation:            int           = 0
    agent_origin:          str           = "unknown"
    epoch_id:              str           = ""
    source_context_hash:   str           = ""
    # v3 semantic diff field — optional Python source for AST-based scoring
    python_content:        Optional[str] = None
    operator_key:          str           = "static"
    operator_category:     str           = "baseline"
    operator_version:      str           = "1.0.0"
    operator_rank:         int           = 0


@dataclass(frozen=True)
class MutationScore:
    """Scored evaluation of a MutationCandidate."""
    mutation_id:         str
    score:               float
    accepted:            bool
    dimension_breakdown: Optional[Dict[str, float]] = None
    warnings:            Optional[List[str]]         = None
    # v2 passthrough lineage fields
    epoch_id:            str                         = ""
    parent_id:           Optional[str]               = None
    agent_origin:        str                         = "unknown"
    elitism_applied:     bool                        = False


# ---------------------------------------------------------------------------
# Scoring Engine
# ---------------------------------------------------------------------------


def score_candidate(
    candidate:            MutationCandidate,
    acceptance_threshold: float                    = DEFAULT_ACCEPTANCE_THRESHOLD,
    weights:              Optional[ScoringWeights]  = None,
    population_state:     Optional[PopulationState] = None,
) -> MutationScore:
    """
    Compute a deterministic, bounded composite mutation score.

    v2 additions (all backward-compatible via optional kwargs):
    - Accepts ScoringWeights; falls back to v1 COMPOSITE_WEIGHTS when None.
    - Accepts PopulationState for adaptive threshold + elitism bonus.
    - Propagates lineage fields from candidate into returned MutationScore.

    v3 addition:
    - When candidate.python_content is set, SemanticDiffEngine replaces the
      risk_score and complexity fields with AST-derived values before scoring.
      The original candidate fields are used as fallback when parsing fails.

    Returns a MutationScore with:
    - score in [0.0, 1.0] (hard-clamped)
    - accepted=True when score >= adjusted_threshold AND no hard violations
    - dimension_breakdown for governance audit
    - warnings for out-of-range inputs
    """
    warnings_list: List[str] = []

    # ── v3: Semantic enrichment of risk_score and complexity ──────────────
    effective_risk_score = float(candidate.risk_score)
    effective_complexity = float(candidate.complexity)
    semantic_active = False

    if candidate.python_content is not None:
        python_digest = _stable_text_digest(candidate.python_content)
        sem_risk, sem_complexity, semantic_active = _semantic_feature_from_digest(
            python_digest,
            candidate.python_content,
        )
        if semantic_active:
            effective_risk_score = sem_risk
            effective_complexity = sem_complexity

    # Weight resolution (v2: prefer ScoringWeights; fallback to v1 dict)
    if weights is not None:
        w_dict = weights.as_composite_dict()
        base_threshold = weights.acceptance_threshold
    elif candidate.weight_override is not None:
        w_dict = candidate.weight_override
        base_threshold = acceptance_threshold
    else:
        w_dict = COMPOSITE_WEIGHTS
        base_threshold = acceptance_threshold

    # Adaptive threshold (v2)
    diversity_pressure = (
        population_state.diversity_pressure if population_state is not None else 0.0
    )
    adjusted_threshold = base_threshold * (1.0 - (diversity_pressure * 0.4))

    # horizon_roi normalisation (v1 invariant preserved)
    horizon_factor = max(0.10, float(candidate.strategic_horizon))
    horizon_roi_raw = float(candidate.forecast_roi) / horizon_factor
    if horizon_roi_raw > 1.0:
        warnings_list.append(f"horizon_roi_clamped:{horizon_roi_raw:.4f}->1.0")
    horizon_roi = min(1.0, max(0.0, horizon_roi_raw))

    # Input range warnings (use original candidate fields for range validation)
    if not (0.0 <= candidate.expected_gain <= 1.0):
        warnings_list.append(f"expected_gain_out_of_range:{candidate.expected_gain}")
    if not (0.0 <= candidate.risk_score <= 1.0):
        warnings_list.append(f"risk_score_out_of_range:{candidate.risk_score}")
    if not (0.0 <= candidate.complexity <= 1.0):
        warnings_list.append(f"complexity_out_of_range:{candidate.complexity}")
    if not (0.0 <= candidate.coverage_delta <= 1.0):
        warnings_list.append(f"coverage_delta_out_of_range:{candidate.coverage_delta}")

    # Dimension contributions (use semantic-enriched values when available)
    eg_contrib  = float(candidate.expected_gain) * w_dict.get("expected_gain", 0.35)
    cd_contrib  = float(candidate.coverage_delta) * w_dict.get("coverage_delta", 0.25)
    hr_contrib  = horizon_roi * w_dict.get("horizon_roi", 0.20)
    risk_pen    = effective_risk_score * w_dict.get("risk_penalty", 0.20)
    complex_pen = effective_complexity * w_dict.get("complexity_penalty", 0.10)

    raw = eg_contrib + cd_contrib + hr_contrib - risk_pen - complex_pen
    base_score = round(min(HARD_CEILING, max(HARD_FLOOR, raw)), 4)

    # Elitism bonus (v2) — applied AFTER threshold computation
    elitism_applied = False
    if (
        population_state is not None
        and candidate.parent_id is not None
        and candidate.parent_id in population_state.elite_ids
    ):
        base_score = round(min(HARD_CEILING, base_score + ELITISM_BONUS), 4)
        elitism_applied = True

    score = base_score

    novelty_signal, lineage_distance, regression_risk = _tie_break_signals(candidate)

    breakdown: Dict[str, float] = {
        "expected_gain_contrib":      round(eg_contrib, 4),
        "coverage_delta_contrib":     round(cd_contrib, 4),
        "horizon_roi_contrib":        round(hr_contrib, 4),
        "risk_penalty_contrib":       round(-risk_pen, 4),
        "complexity_penalty_contrib": round(-complex_pen, 4),
        "raw_before_clamp":           round(raw, 4),
        "diversity_pressure":         round(diversity_pressure, 4),
        "adjusted_threshold":         round(adjusted_threshold, 4),
        "novelty_signal":             round(novelty_signal, 6),
        "lineage_distance":           round(lineage_distance, 4),
        "regression_risk":            round(regression_risk, 4),
        "semantic_scoring_active":    1.0 if semantic_active else 0.0,
    }

    has_hard_violation = any("_out_of_range" in w for w in warnings_list)
    accepted = (score >= adjusted_threshold) and not has_hard_violation

    return MutationScore(
        mutation_id=candidate.mutation_id,
        score=score,
        accepted=accepted,
        dimension_breakdown=breakdown,
        warnings=warnings_list if warnings_list else None,
        epoch_id=candidate.epoch_id,
        parent_id=candidate.parent_id,
        agent_origin=candidate.agent_origin,
        elitism_applied=elitism_applied,
    )




def apply_operator_registry(
    candidates: list[MutationCandidate],
    *,
    outcome_history: Mapping[str, "OperatorOutcome"] | None = None,
    profile: "OperatorSelectionProfile | None" = None,
) -> list[MutationCandidate]:
    """Apply deterministic operator transforms before scoring/ranking."""
    from runtime.evolution.mutation_operator_framework import MutationOperatorRegistry

    registry = MutationOperatorRegistry()
    result: list[MutationCandidate] = []
    for candidate in candidates:
        if not hasattr(candidate, "mutation_id"):
            result.append(candidate)
            continue
        try:
            result.append(
                registry.apply_operator(candidate, outcome_history=outcome_history, profile=profile)
            )
        except Exception:
            result.append(candidate)
    return result


def rank_candidates_via_registry(
    candidates: list[MutationCandidate],
    acceptance_threshold: float = DEFAULT_ACCEPTANCE_THRESHOLD,
    weights: Optional[ScoringWeights] = None,
    population_state: Optional[PopulationState] = None,
    *,
    outcome_history: Mapping[str, "OperatorOutcome"] | None = None,
    profile: "OperatorSelectionProfile | None" = None,
) -> list[MutationScore]:
    """Apply operator selection and then rank resulting candidates."""
    enriched = apply_operator_registry(
        candidates,
        outcome_history=outcome_history,
        profile=profile,
    )
    return rank_mutation_candidates(
        enriched,
        acceptance_threshold=acceptance_threshold,
        weights=weights,
        population_state=population_state,
    )


def rank_mutation_candidates(
    candidates:           list[MutationCandidate],
    acceptance_threshold: float                    = DEFAULT_ACCEPTANCE_THRESHOLD,
    weights:              Optional[ScoringWeights]  = None,
    population_state:     Optional[PopulationState] = None,
) -> list[MutationScore]:
    """
    Score and sort all candidates, highest score first.

    Accepts the same optional v2 kwargs as score_candidate; omitting them
    reproduces v1 behaviour identically.
    """
    indexed_scores = []
    for idx, candidate in enumerate(candidates):
        scored = score_candidate(
            candidate,
            acceptance_threshold=acceptance_threshold,
            weights=weights,
            population_state=population_state,
        )
        novelty_signal, lineage_distance, regression_risk = _tie_break_signals(candidate)
        indexed_scores.append(
            (
                idx,
                scored,
                novelty_signal,
                lineage_distance,
                regression_risk,
            )
        )

    return [
        scored
        for _, scored, _, _, _ in sorted(
            indexed_scores,
            key=lambda item: (
                -item[1].score,
                item[1].mutation_id,  # stable primary tiebreaker (alphabetical)
                -item[2],             # novelty signal (secondary)
                -item[3],             # lineage distance
                item[4],              # regression risk
                item[0],              # insertion order
            ),
        )
    ]
