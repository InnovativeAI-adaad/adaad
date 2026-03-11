# SPDX-License-Identifier: Apache-2.0
"""Tests for ADAAD-8 Policy Simulation DSL Grammar."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.governance.simulation.dsl_grammar import (
    DSL_GRAMMAR_VERSION,
    ConstraintType,
    SimulationDSLError,
    parse_constraint,
    parse_policy_block,
)


# ---------------------------------------------------------------------------
# Happy path: all 10 constraint types
# ---------------------------------------------------------------------------

class TestParseConstraintHappyPath:
    def test_require_approvals(self):
        expr = parse_constraint("require_approvals(tier=PRODUCTION, count=3)")
        assert expr.constraint_type == ConstraintType.REQUIRE_APPROVALS
        assert expr.kwargs["tier"] == "PRODUCTION"
        assert expr.kwargs["count"] == 3
        assert isinstance(expr.kwargs["count"], int)

    def test_max_risk_score(self):
        expr = parse_constraint("max_risk_score(threshold=0.4)")
        assert expr.constraint_type == ConstraintType.MAX_RISK_SCORE
        assert abs(expr.kwargs["threshold"] - 0.4) < 1e-9
        assert isinstance(expr.kwargs["threshold"], float)

    def test_max_mutations_per_epoch(self):
        expr = parse_constraint("max_mutations_per_epoch(count=10)")
        assert expr.constraint_type == ConstraintType.MAX_MUTATIONS_PER_EPOCH
        assert expr.kwargs["count"] == 10

    def test_max_complexity_delta(self):
        expr = parse_constraint("max_complexity_delta(delta=0.15)")
        assert expr.constraint_type == ConstraintType.MAX_COMPLEXITY_DELTA
        assert abs(expr.kwargs["delta"] - 0.15) < 1e-9

    def test_freeze_tier(self):
        expr = parse_constraint('freeze_tier(tier=PRODUCTION, reason="audit period")')
        assert expr.constraint_type == ConstraintType.FREEZE_TIER
        assert expr.kwargs["tier"] == "PRODUCTION"
        assert "audit period" in expr.kwargs.get("reason", "")

    def test_freeze_tier_no_reason(self):
        expr = parse_constraint("freeze_tier(tier=STAGING)")
        assert expr.constraint_type == ConstraintType.FREEZE_TIER
        assert expr.kwargs["tier"] == "STAGING"

    def test_require_rule(self):
        expr = parse_constraint("require_rule(rule_id=lineage_continuity, severity=BLOCKING)")
        assert expr.constraint_type == ConstraintType.REQUIRE_RULE
        assert expr.kwargs["rule_id"] == "lineage_continuity"
        assert expr.kwargs["severity"] == "BLOCKING"

    def test_require_rule_default_severity(self):
        expr = parse_constraint("require_rule(rule_id=lineage_continuity)")
        assert expr.constraint_type == ConstraintType.REQUIRE_RULE

    def test_min_test_coverage(self):
        expr = parse_constraint("min_test_coverage(threshold=0.80)")
        assert expr.constraint_type == ConstraintType.MIN_TEST_COVERAGE
        assert abs(expr.kwargs["threshold"] - 0.80) < 1e-9

    def test_max_entropy_per_epoch(self):
        expr = parse_constraint("max_entropy_per_epoch(ceiling=0.30)")
        assert expr.constraint_type == ConstraintType.MAX_ENTROPY_PER_EPOCH
        assert abs(expr.kwargs["ceiling"] - 0.30) < 1e-9

    def test_escalate_reviewers_on_risk(self):
        expr = parse_constraint("escalate_reviewers_on_risk(threshold=0.6, count=2)")
        assert expr.constraint_type == ConstraintType.ESCALATE_REVIEWERS_ON_RISK
        assert abs(expr.kwargs["threshold"] - 0.6) < 1e-9
        assert expr.kwargs["count"] == 2

    def test_require_lineage_depth(self):
        expr = parse_constraint("require_lineage_depth(min=3)")
        assert expr.constraint_type == ConstraintType.REQUIRE_LINEAGE_DEPTH
        assert expr.kwargs["min"] == 3


# ---------------------------------------------------------------------------
# Grammar version recorded
# ---------------------------------------------------------------------------

class TestGrammarVersion:
    def test_grammar_version_in_expression(self):
        expr = parse_constraint("max_risk_score(threshold=0.5)")
        assert expr.grammar_version == DSL_GRAMMAR_VERSION

    def test_raw_expression_preserved(self):
        raw = "max_risk_score(threshold=0.5)"
        expr = parse_constraint(raw)
        assert raw in expr.raw_expression


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

class TestParseConstraintErrors:
    def test_unknown_constraint_type_raises(self):
        with pytest.raises(SimulationDSLError, match="Unknown constraint type"):
            parse_constraint("nonexistent_constraint(foo=bar)")

    def test_missing_parentheses_raises(self):
        with pytest.raises(SimulationDSLError, match="form"):
            parse_constraint("max_risk_score")

    def test_missing_required_param_raises(self):
        with pytest.raises(SimulationDSLError, match="threshold"):
            parse_constraint("max_risk_score()")

    def test_count_zero_raises_for_require_approvals(self):
        with pytest.raises(SimulationDSLError):
            parse_constraint("require_approvals(tier=PRODUCTION, count=0)")

    def test_threshold_out_of_range_raises(self):
        with pytest.raises(SimulationDSLError, match="out of range"):
            parse_constraint("max_risk_score(threshold=1.5)")

    def test_invalid_severity_raises(self):
        with pytest.raises(SimulationDSLError, match="BLOCKING|WARNING|INFO"):
            parse_constraint("require_rule(rule_id=my_rule, severity=INVALID)")

    def test_non_numeric_count_raises(self):
        with pytest.raises(SimulationDSLError):
            parse_constraint("require_approvals(tier=PRODUCTION, count=abc)")

    def test_error_carries_token(self):
        try:
            parse_constraint("bad_constraint(x=1)")
        except SimulationDSLError as exc:
            assert exc.token


# ---------------------------------------------------------------------------
# parse_policy_block
# ---------------------------------------------------------------------------

class TestParsePolicyBlock:
    def test_multi_line_block(self):
        block = """
        require_approvals(tier=PRODUCTION, count=3)
        max_risk_score(threshold=0.4)
        min_test_coverage(threshold=0.80)
        """
        exprs = parse_policy_block(block)
        assert len(exprs) == 3
        assert exprs[0].constraint_type == ConstraintType.REQUIRE_APPROVALS
        assert exprs[1].constraint_type == ConstraintType.MAX_RISK_SCORE
        assert exprs[2].constraint_type == ConstraintType.MIN_TEST_COVERAGE

    def test_comments_skipped(self):
        block = """
        # This is a comment
        max_risk_score(threshold=0.5)
        # Another comment
        """
        exprs = parse_policy_block(block)
        assert len(exprs) == 1

    def test_blank_lines_skipped(self):
        block = "\n\n\nmax_risk_score(threshold=0.5)\n\n"
        exprs = parse_policy_block(block)
        assert len(exprs) == 1

    def test_empty_block(self):
        exprs = parse_policy_block("")
        assert exprs == []

    def test_error_includes_line_number(self):
        block = "max_risk_score(threshold=0.5)\nbad_thing()\n"
        with pytest.raises(SimulationDSLError, match="line 2"):
            parse_policy_block(block)

    def test_all_ten_constraint_types_parse(self):
        block = """
require_approvals(tier=PRODUCTION, count=3)
max_risk_score(threshold=0.4)
max_mutations_per_epoch(count=10)
max_complexity_delta(delta=0.15)
freeze_tier(tier=PRODUCTION, reason=audit)
require_rule(rule_id=lineage_continuity, severity=BLOCKING)
min_test_coverage(threshold=0.80)
max_entropy_per_epoch(ceiling=0.30)
escalate_reviewers_on_risk(threshold=0.6, count=2)
require_lineage_depth(min=3)
"""
        exprs = parse_policy_block(block)
        assert len(exprs) == 10
        types = [e.constraint_type for e in exprs]
        for ct in ConstraintType:
            assert ct in types
