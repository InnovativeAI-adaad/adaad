# SPDX-License-Identifier: Apache-2.0
"""Tests for runtime.evolution.mutation_route_optimizer."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.evolution.mutation_route_optimizer import (
    MutationRouteOptimizer,
    RouteTier,
    RouteDecision,
    ROUTE_VERSION,
    trivial_route_score,
)


@pytest.fixture()
def optimizer() -> MutationRouteOptimizer:
    return MutationRouteOptimizer()


# ---------------------------------------------------------------------------
# TRIVIAL routing
# ---------------------------------------------------------------------------


def test_zero_loc_delta_is_trivial(optimizer):
    decision = optimizer.route(
        mutation_id="mut_001",
        intent="refactor",
        ops=[{"type": "refactor"}],
        files_touched=["app/main.py"],
        loc_added=0,
        loc_deleted=0,
    )
    assert decision.tier is RouteTier.TRIVIAL
    assert decision.skip_heavy_scoring is True
    assert decision.require_human_review is False
    assert "trivial_zero_loc_delta" in decision.reasons


def test_doc_update_intent_small_delta_is_trivial(optimizer):
    decision = optimizer.route(
        mutation_id="mut_002",
        intent="doc_update",
        ops=[{"type": "doc_update"}],
        files_touched=["README.md"],
        loc_added=5,
        loc_deleted=3,
    )
    assert decision.tier is RouteTier.TRIVIAL
    assert decision.skip_heavy_scoring is True


def test_doc_ops_on_md_files_are_trivial(optimizer):
    decision = optimizer.route(
        mutation_id="mut_003",
        intent="documentation",
        ops=[{"type": "doc_update"}, {"type": "comment_update"}],
        files_touched=["docs/README.md", "CHANGELOG.md"],
        loc_added=10,
        loc_deleted=2,
    )
    assert decision.tier is RouteTier.TRIVIAL


# ---------------------------------------------------------------------------
# ELEVATED routing
# ---------------------------------------------------------------------------


def test_governance_path_is_elevated(optimizer):
    decision = optimizer.route(
        mutation_id="mut_010",
        intent="refactor",
        ops=[{"type": "refactor"}],
        files_touched=["runtime/governance/gate.py"],
        loc_added=15,
        loc_deleted=5,
    )
    assert decision.tier is RouteTier.ELEVATED
    assert decision.require_human_review is True
    assert decision.skip_heavy_scoring is False


def test_security_path_is_elevated(optimizer):
    decision = optimizer.route(
        mutation_id="mut_011",
        intent="harden",
        ops=[{"type": "security_fix"}],
        files_touched=["security/cryovant.py"],
        loc_added=20,
        loc_deleted=0,
    )
    assert decision.tier is RouteTier.ELEVATED


def test_elevated_intent_keyword_escalates(optimizer):
    decision = optimizer.route(
        mutation_id="mut_012",
        intent="ledger_compaction",
        ops=[{"type": "compact"}],
        files_touched=["data/ledger.jsonl"],
        loc_added=1,
        loc_deleted=1,
    )
    assert decision.tier is RouteTier.ELEVATED


def test_critical_risk_tag_escalates(optimizer):
    decision = optimizer.route(
        mutation_id="mut_013",
        intent="refactor",
        ops=[{"type": "refactor"}],
        files_touched=["app/main.py"],
        loc_added=50,
        loc_deleted=30,
        risk_tags=["CRITICAL"],
    )
    assert decision.tier is RouteTier.ELEVATED


def test_security_risk_tag_escalates(optimizer):
    decision = optimizer.route(
        mutation_id="mut_014",
        intent="fix",
        ops=[{"type": "fix"}],
        files_touched=["app/auth.py"],
        loc_added=10,
        loc_deleted=5,
        risk_tags=["SECURITY"],
    )
    assert decision.tier is RouteTier.ELEVATED


# ---------------------------------------------------------------------------
# STANDARD routing
# ---------------------------------------------------------------------------


def test_normal_refactor_is_standard(optimizer):
    decision = optimizer.route(
        mutation_id="mut_020",
        intent="refactor",
        ops=[{"type": "refactor"}],
        files_touched=["app/utils.py"],
        loc_added=25,
        loc_deleted=10,
    )
    assert decision.tier is RouteTier.STANDARD
    assert decision.skip_heavy_scoring is False
    assert decision.require_human_review is False


def test_default_reason_present_for_standard(optimizer):
    decision = optimizer.route(
        mutation_id="mut_021",
        intent="perf",
        ops=[{"type": "optimize"}],
        files_touched=["app/runner.py"],
        loc_added=5,
        loc_deleted=5,
    )
    assert decision.tier is RouteTier.STANDARD
    assert "default_standard_route" in decision.reasons


# ---------------------------------------------------------------------------
# ELEVATED overrides TRIVIAL
# ---------------------------------------------------------------------------


def test_elevated_overrides_trivial_zero_loc(optimizer):
    """A zero-LOC-delta mutation on a governance path must still be ELEVATED."""
    decision = optimizer.route(
        mutation_id="mut_030",
        intent="doc_update",
        ops=[{"type": "doc_update"}],
        files_touched=["runtime/governance/gate.py"],
        loc_added=0,
        loc_deleted=0,
    )
    assert decision.tier is RouteTier.ELEVATED


# ---------------------------------------------------------------------------
# Decision digest determinism
# ---------------------------------------------------------------------------


def test_identical_inputs_produce_identical_digest(optimizer):
    kwargs = dict(
        mutation_id="mut_040",
        intent="refactor",
        ops=[{"type": "refactor"}],
        files_touched=["app/main.py"],
        loc_added=10,
        loc_deleted=5,
    )
    d1 = optimizer.route(**kwargs)
    d2 = optimizer.route(**kwargs)
    assert d1.decision_digest == d2.decision_digest


def test_different_files_produce_different_digest(optimizer):
    base = dict(
        mutation_id="mut_041",
        intent="refactor",
        ops=[{"type": "refactor"}],
        loc_added=10,
        loc_deleted=5,
    )
    d1 = optimizer.route(files_touched=["app/main.py"], **base)
    d2 = optimizer.route(files_touched=["runtime/governance/gate.py"], **base)
    assert d1.decision_digest != d2.decision_digest


# ---------------------------------------------------------------------------
# RouteDecision.to_payload
# ---------------------------------------------------------------------------


def test_to_payload_roundtrip(optimizer):
    decision = optimizer.route(
        mutation_id="mut_050",
        intent="refactor",
        ops=[],
        files_touched=[],
        loc_added=0,
        loc_deleted=0,
    )
    payload = decision.to_payload()
    assert payload["mutation_id"] == "mut_050"
    assert payload["tier"] == decision.tier.value
    assert payload["route_version"] == ROUTE_VERSION
    assert payload["decision_digest"] == decision.decision_digest


# ---------------------------------------------------------------------------
# trivial_route_score
# ---------------------------------------------------------------------------


def test_trivial_route_score_structure():
    score = trivial_route_score()
    assert score["fast_path"] is True
    assert score["passed_constitution"] is True
    assert 0.0 <= score["score"] <= 1.0
    assert score["tier"] == RouteTier.TRIVIAL.value
