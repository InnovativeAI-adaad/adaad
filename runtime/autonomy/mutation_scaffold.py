# SPDX-License-Identifier: Apache-2.0
"""Deterministic mutation scaffolding and scoring helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MutationCandidate:
    mutation_id: str
    expected_gain: float
    risk_score: float
    complexity: float
    coverage_delta: float
    strategic_horizon: float = 1.0
    forecast_roi: float = 0.0


@dataclass(frozen=True)
class MutationScore:
    mutation_id: str
    score: float
    accepted: bool


def score_candidate(candidate: MutationCandidate, acceptance_threshold: float = 0.25) -> MutationScore:
    horizon_factor = max(0.1, candidate.strategic_horizon)
    horizon_roi = candidate.forecast_roi / horizon_factor
    weighted = (
        (candidate.expected_gain * 0.35)
        + (candidate.coverage_delta * 0.25)
        + (horizon_roi * 0.20)
        - (candidate.risk_score * 0.20)
        - (candidate.complexity * 0.10)
    )
    score = round(weighted, 4)
    return MutationScore(mutation_id=candidate.mutation_id, score=score, accepted=score >= acceptance_threshold)


def rank_mutation_candidates(candidates: list[MutationCandidate], acceptance_threshold: float = 0.25) -> list[MutationScore]:
    scores = [score_candidate(candidate, acceptance_threshold=acceptance_threshold) for candidate in candidates]
    return sorted(scores, key=lambda item: (-item.score, item.mutation_id))
