# SPDX-License-Identifier: Apache-2.0
"""Phase 16 — CritiqueModule strategy-weighted dimension floor tests (10 tests, T16-03-01..10)."""

import pytest

from runtime.intelligence.critique import (
    DIMENSION_FLOORS,
    STRATEGY_FLOOR_OVERRIDES,
    CritiqueModule,
    _effective_floors,
)
from runtime.intelligence.strategy import STRATEGY_TAXONOMY


def _make_proposal(
    *,
    proposal_id: str = "test:proposal-01",
    title: str = "Test mutation proposal fixture",
    summary: str = "A controlled mutation proposal for testing CritiqueModule Phase 16.",
    estimated_impact: float = 0.5,
    real_diff: str = "+ x = 1\n- x = 0\n",
    evidence: dict | None = None,
    target_files: tuple = (),
    projected_impact: dict | None = None,
):
    from runtime.intelligence.proposal import Proposal
    from dataclasses import dataclass

    class _FakeProposal:
        pass

    p = _FakeProposal()
    p.proposal_id = proposal_id
    p.title = title
    p.summary = summary
    p.estimated_impact = estimated_impact
    p.real_diff = real_diff
    p.evidence = evidence or {"replay_digest": "abc123"}
    p.target_files = target_files
    p.projected_impact = projected_impact or {"quality": 0.7}
    return p


module = CritiqueModule()


# T16-03-01  _effective_floors never lowers a baseline floor
def test_effective_floors_never_lower_baseline() -> None:
    for strategy_id in STRATEGY_TAXONOMY:
        floors = _effective_floors(strategy_id)
        for dim in DIMENSION_FLOORS:
            assert floors[dim] >= DIMENSION_FLOORS[dim], (
                f"Floor for dim={dim} strategy={strategy_id} is {floors[dim]} "
                f"< baseline {DIMENSION_FLOORS[dim]}"
            )


# T16-03-02  safety_hardening has the highest governance floor
def test_safety_hardening_has_highest_governance_floor() -> None:
    safety_floors = _effective_floors("safety_hardening")
    for strategy_id in STRATEGY_TAXONOMY:
        if strategy_id == "safety_hardening":
            continue
        other_floors = _effective_floors(strategy_id)
        assert safety_floors["governance"] >= other_floors["governance"], (
            f"safety_hardening governance floor should be highest; "
            f"got {safety_floors['governance']} vs {strategy_id}: {other_floors['governance']}"
        )


# T16-03-03  conservative_hold has the highest risk floor
def test_conservative_hold_has_highest_risk_floor() -> None:
    conservative_floors = _effective_floors("conservative_hold")
    # baseline risk floor is 0.30; conservative raises to 0.55
    assert conservative_floors["risk"] > DIMENSION_FLOORS["risk"]
    assert conservative_floors["risk"] == 0.55


# T16-03-04  Unknown strategy_id returns baseline floors
def test_unknown_strategy_id_returns_baseline() -> None:
    floors = _effective_floors("unknown_strategy_xyz")
    assert floors == DIMENSION_FLOORS


# T16-03-05  None strategy_id returns baseline floors
def test_none_strategy_id_returns_baseline() -> None:
    floors = _effective_floors(None)
    assert floors == DIMENSION_FLOORS


# T16-03-06  review() without strategy_id uses baseline (backward compat)
def test_review_without_strategy_id_uses_baseline() -> None:
    proposal = _make_proposal()
    result = module.review(proposal)
    assert result.metadata.get("strategy_id") == "baseline"
    assert result.algorithm_version == "v2.0.0"


# T16-03-07  review() with strategy_id includes strategy in metadata
def test_review_with_strategy_id_recorded_in_metadata() -> None:
    proposal = _make_proposal()
    result = module.review(proposal, strategy_id="test_coverage_expansion")
    assert result.metadata.get("strategy_id") == "test_coverage_expansion"
    assert result.metadata.get("critique_taxonomy_version") == "16.0"


# T16-03-08  review_digest differs between baseline and strategy-specific reviews
def test_review_digest_includes_strategy_id() -> None:
    proposal = _make_proposal()
    r_baseline = module.review(proposal)
    r_strategy = module.review(proposal, strategy_id="safety_hardening")
    assert r_baseline.review_digest != r_strategy.review_digest


# T16-03-09  STRATEGY_FLOOR_OVERRIDES only contains taxonomy members as keys
def test_strategy_floor_overrides_keys_are_valid_taxonomy_members() -> None:
    for strategy_id in STRATEGY_FLOOR_OVERRIDES:
        assert strategy_id in STRATEGY_TAXONOMY, (
            f"STRATEGY_FLOOR_OVERRIDES contains unknown strategy_id '{strategy_id}'"
        )


# T16-03-10  review() is deterministic: same proposal + strategy → same digest
def test_review_is_deterministic() -> None:
    proposal = _make_proposal()
    results = [module.review(proposal, strategy_id="structural_refactor") for _ in range(3)]
    digests = {r.review_digest for r in results}
    assert len(digests) == 1, "review_digest should be identical across runs"
