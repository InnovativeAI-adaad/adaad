# SPDX-License-Identifier: Apache-2.0
"""Tests: Policy Simulation DSL Grammar + Constraint Interpreter — ADAAD-8 / PR-10

Tests cover:
- parse_constraint: all 10 constraint types, malformed input rejection
- parse_policy_block: multi-line blocks, comments, blank lines
- interpret_policy: all 10 types, duplicate rejection, simulation=True invariant
- interpret_policy_block: end-to-end DSL text → SimulationPolicy
- SimulationPolicy: structural invariants, to_dict(), is_tier_frozen()
- SimulationPolicy.simulation cannot be False
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
pytestmark = pytest.mark.governance_gate

from runtime.governance.simulation.dsl_grammar import (
    ConstraintExpression,
    ConstraintType,
    DSL_GRAMMAR_VERSION,
    SimulationDSLError,
    parse_constraint,
    parse_policy_block,
)
from runtime.governance.simulation.constraint_interpreter import (
    SimulationPolicy,
    SimulationPolicyError,
    interpret_policy,
    interpret_policy_block,
)


# ---------------------------------------------------------------------------
# Grammar: parse_constraint — all 10 types
# ---------------------------------------------------------------------------

class TestParseConstraintAllTypes:
    def test_require_approvals(self):
        expr = parse_constraint("require_approvals(tier=PRODUCTION, count=3)")
        assert expr.constraint_type == ConstraintType.REQUIRE_APPROVALS
        assert expr.kwargs["tier"] == "PRODUCTION"
        assert expr.kwargs["count"] == 3

    def test_max_risk_score(self):
        expr = parse_constraint("max_risk_score(threshold=0.4)")
        assert expr.constraint_type == ConstraintType.MAX_RISK_SCORE
        assert expr.kwargs["threshold"] == pytest.approx(0.4)

    def test_max_mutations_per_epoch(self):
        expr = parse_constraint("max_mutations_per_epoch(count=10)")
        assert expr.constraint_type == ConstraintType.MAX_MUTATIONS_PER_EPOCH
        assert expr.kwargs["count"] == 10

    def test_max_complexity_delta(self):
        expr = parse_constraint("max_complexity_delta(delta=0.15)")
        assert expr.constraint_type == ConstraintType.MAX_COMPLEXITY_DELTA
        assert expr.kwargs["delta"] == pytest.approx(0.15)

    def test_freeze_tier(self):
        expr = parse_constraint("freeze_tier(tier=PRODUCTION, reason=\"audit period\")")
        assert expr.constraint_type == ConstraintType.FREEZE_TIER
        assert expr.kwargs["tier"] == "PRODUCTION"
        assert "reason" in expr.kwargs

    def test_freeze_tier_without_reason(self):
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
        assert expr.kwargs["threshold"] == pytest.approx(0.80)

    def test_max_entropy_per_epoch(self):
        expr = parse_constraint("max_entropy_per_epoch(ceiling=0.30)")
        assert expr.constraint_type == ConstraintType.MAX_ENTROPY_PER_EPOCH
        assert expr.kwargs["ceiling"] == pytest.approx(0.30)

    def test_escalate_reviewers_on_risk(self):
        expr = parse_constraint("escalate_reviewers_on_risk(threshold=0.6, count=2)")
        assert expr.constraint_type == ConstraintType.ESCALATE_REVIEWERS_ON_RISK
        assert expr.kwargs["threshold"] == pytest.approx(0.6)
        assert expr.kwargs["count"] == 2

    def test_require_lineage_depth(self):
        expr = parse_constraint("require_lineage_depth(min=3)")
        assert expr.constraint_type == ConstraintType.REQUIRE_LINEAGE_DEPTH
        assert expr.kwargs["min"] == 3


# ---------------------------------------------------------------------------
# Grammar: malformed input rejection
# ---------------------------------------------------------------------------

class TestParseConstraintErrors:
    def test_unknown_constraint_type_raises(self):
        with pytest.raises(SimulationDSLError) as exc_info:
            parse_constraint("unknown_constraint(foo=bar)")
        assert "unknown_constraint" in str(exc_info.value).lower() or \
               "unknown" in str(exc_info.value).lower()

    def test_missing_parentheses_raises(self):
        with pytest.raises(SimulationDSLError):
            parse_constraint("max_risk_score threshold=0.4")

    def test_empty_expression_raises(self):
        with pytest.raises(SimulationDSLError):
            parse_constraint("")

    def test_missing_required_param_raises(self):
        with pytest.raises(SimulationDSLError):
            parse_constraint("require_approvals(tier=PRODUCTION)")  # missing count

    def test_out_of_range_float_raises(self):
        with pytest.raises(SimulationDSLError):
            parse_constraint("max_risk_score(threshold=1.5)")

    def test_negative_int_raises(self):
        with pytest.raises(SimulationDSLError):
            parse_constraint("require_approvals(tier=PRODUCTION, count=0)")

    def test_non_numeric_float_raises(self):
        with pytest.raises(SimulationDSLError):
            parse_constraint("max_risk_score(threshold=not_a_number)")

    def test_non_numeric_count_raises(self):
        with pytest.raises(SimulationDSLError):
            parse_constraint("require_approvals(tier=PRODUCTION, count=abc)")

    def test_invalid_severity_raises(self):
        with pytest.raises(SimulationDSLError):
            parse_constraint("require_rule(rule_id=foo, severity=FATAL)")

    def test_error_carries_token(self):
        with pytest.raises(SimulationDSLError) as exc_info:
            parse_constraint("bad_constraint(x=1)")
        assert exc_info.value.token


# ---------------------------------------------------------------------------
# Grammar: parse_policy_block
# ---------------------------------------------------------------------------

class TestParsePolicyBlock:
    def test_multi_line_block(self):
        block = """
        require_approvals(tier=PRODUCTION, count=3)
        max_risk_score(threshold=0.4)
        """
        exprs = parse_policy_block(block)
        assert len(exprs) == 2
        assert exprs[0].constraint_type == ConstraintType.REQUIRE_APPROVALS
        assert exprs[1].constraint_type == ConstraintType.MAX_RISK_SCORE

    def test_comments_and_blank_lines_skipped(self):
        block = """
        # This is a comment
        max_risk_score(threshold=0.4)

        # Another comment
        max_mutations_per_epoch(count=5)
        """
        exprs = parse_policy_block(block)
        assert len(exprs) == 2

    def test_empty_block_returns_empty_list(self):
        exprs = parse_policy_block("   \n  \n  ")
        assert exprs == []

    def test_parse_error_includes_line_number(self):
        block = "max_risk_score(threshold=0.4)\nbad_constraint(foo=bar)"
        with pytest.raises(SimulationDSLError) as exc_info:
            parse_policy_block(block)
        assert "line 2" in str(exc_info.value)

    def test_grammar_version_in_each_expression(self):
        exprs = parse_policy_block("max_risk_score(threshold=0.5)")
        assert exprs[0].grammar_version == DSL_GRAMMAR_VERSION

    def test_blank_lines_skipped(self):
        exprs = parse_policy_block("\n\n\nmax_risk_score(threshold=0.5)\n\n")
        assert len(exprs) == 1

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
        parsed_types = {e.constraint_type for e in exprs}
        expected_types = set(ConstraintType.__members__.values())
        assert parsed_types == expected_types


class TestGrammarVersion:
    def test_grammar_version_in_expression(self):
        expr = parse_constraint("max_risk_score(threshold=0.5)")
        assert expr.grammar_version == DSL_GRAMMAR_VERSION

    def test_raw_expression_preserved(self):
        raw = "max_risk_score(threshold=0.5)"
        expr = parse_constraint(raw)
        assert raw in expr.raw_expression


# ---------------------------------------------------------------------------
# Interpreter: interpret_policy — all 10 constraint types
# ---------------------------------------------------------------------------

class TestInterpretPolicyAllTypes:
    def test_empty_expressions_produces_empty_policy(self):
        policy = interpret_policy([])
        assert policy.simulation is True
        assert policy.constraint_count == 0
        assert policy.require_approvals is None
        assert policy.max_risk_score is None
        assert policy.freeze_tiers == []
        assert policy.require_rules == []

    def test_require_approvals(self):
        exprs = parse_policy_block("require_approvals(tier=PRODUCTION, count=3)")
        policy = interpret_policy(exprs)
        assert policy.require_approvals == {"tier": "PRODUCTION", "count": 3}

    def test_max_risk_score(self):
        exprs = parse_policy_block("max_risk_score(threshold=0.35)")
        policy = interpret_policy(exprs)
        assert policy.max_risk_score == pytest.approx(0.35)

    def test_max_mutations_per_epoch(self):
        exprs = parse_policy_block("max_mutations_per_epoch(count=7)")
        policy = interpret_policy(exprs)
        assert policy.max_mutations_per_epoch == 7

    def test_max_complexity_delta(self):
        exprs = parse_policy_block("max_complexity_delta(delta=0.20)")
        policy = interpret_policy(exprs)
        assert policy.max_complexity_delta == pytest.approx(0.20)

    def test_freeze_tier_single(self):
        exprs = parse_policy_block("freeze_tier(tier=PRODUCTION)")
        policy = interpret_policy(exprs)
        assert "PRODUCTION" in policy.freeze_tiers
        assert policy.is_tier_frozen("PRODUCTION") is True
        assert policy.is_tier_frozen("SANDBOX") is False

    def test_freeze_tier_multiple_distinct(self):
        block = "freeze_tier(tier=PRODUCTION)\nfreeze_tier(tier=STAGING)"
        exprs = parse_policy_block(block)
        policy = interpret_policy(exprs)
        assert "PRODUCTION" in policy.freeze_tiers
        assert "STAGING" in policy.freeze_tiers

    def test_require_rule_single(self):
        exprs = parse_policy_block("require_rule(rule_id=lineage_continuity, severity=BLOCKING)")
        policy = interpret_policy(exprs)
        assert len(policy.require_rules) == 1
        assert policy.require_rules[0] == {"rule_id": "lineage_continuity", "severity": "BLOCKING"}

    def test_require_rule_multiple_distinct(self):
        block = (
            "require_rule(rule_id=lineage_continuity, severity=BLOCKING)\n"
            "require_rule(rule_id=ast_validity, severity=WARNING)"
        )
        exprs = parse_policy_block(block)
        policy = interpret_policy(exprs)
        assert len(policy.require_rules) == 2

    def test_min_test_coverage(self):
        exprs = parse_policy_block("min_test_coverage(threshold=0.80)")
        policy = interpret_policy(exprs)
        assert policy.min_test_coverage == pytest.approx(0.80)

    def test_max_entropy_per_epoch(self):
        exprs = parse_policy_block("max_entropy_per_epoch(ceiling=0.25)")
        policy = interpret_policy(exprs)
        assert policy.max_entropy_per_epoch == pytest.approx(0.25)

    def test_escalate_reviewers_on_risk(self):
        exprs = parse_policy_block("escalate_reviewers_on_risk(threshold=0.6, count=2)")
        policy = interpret_policy(exprs)
        assert policy.escalate_reviewers_on_risk == {"threshold": pytest.approx(0.6), "count": 2}

    def test_require_lineage_depth(self):
        exprs = parse_policy_block("require_lineage_depth(min=4)")
        policy = interpret_policy(exprs)
        assert policy.require_lineage_depth == 4


# ---------------------------------------------------------------------------
# Interpreter: simulation=True invariant
# ---------------------------------------------------------------------------

class TestSimulationFlagInvariant:
    def test_simulation_is_always_true_on_empty_policy(self):
        policy = interpret_policy([])
        assert policy.simulation is True

    def test_simulation_is_always_true_with_constraints(self):
        exprs = parse_policy_block("max_risk_score(threshold=0.5)")
        policy = interpret_policy(exprs)
        assert policy.simulation is True

    def test_simulation_policy_raises_if_simulation_false(self):
        """SimulationPolicy cannot be constructed with simulation=False."""
        with pytest.raises(SimulationPolicyError):
            SimulationPolicy(simulation=False)

    def test_simulation_policy_is_frozen(self):
        """SimulationPolicy fields cannot be mutated post-construction."""
        policy = interpret_policy([])
        with pytest.raises((AttributeError, TypeError)):
            policy.simulation = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Interpreter: duplicate constraint rejection
# ---------------------------------------------------------------------------

class TestDuplicateConstraintRejection:
    def test_duplicate_require_approvals_raises(self):
        block = (
            "require_approvals(tier=PRODUCTION, count=2)\n"
            "require_approvals(tier=STAGING, count=3)"
        )
        exprs = parse_policy_block(block)
        with pytest.raises(SimulationPolicyError) as exc_info:
            interpret_policy(exprs)
        assert "require_approvals" in str(exc_info.value)

    def test_duplicate_max_risk_score_raises(self):
        block = "max_risk_score(threshold=0.4)\nmax_risk_score(threshold=0.6)"
        exprs = parse_policy_block(block)
        with pytest.raises(SimulationPolicyError):
            interpret_policy(exprs)

    def test_duplicate_freeze_tier_same_tier_raises(self):
        block = "freeze_tier(tier=PRODUCTION)\nfreeze_tier(tier=PRODUCTION)"
        exprs = parse_policy_block(block)
        with pytest.raises(SimulationPolicyError):
            interpret_policy(exprs)

    def test_duplicate_require_rule_same_rule_id_raises(self):
        block = (
            "require_rule(rule_id=lineage_continuity, severity=BLOCKING)\n"
            "require_rule(rule_id=lineage_continuity, severity=WARNING)"
        )
        exprs = parse_policy_block(block)
        with pytest.raises(SimulationPolicyError):
            interpret_policy(exprs)


# ---------------------------------------------------------------------------
# Interpreter: interpret_policy_block end-to-end
# ---------------------------------------------------------------------------

class TestInterpretPolicyBlock:
    def test_full_block_end_to_end(self):
        block = """
        # Hypothetical strict audit policy
        require_approvals(tier=PRODUCTION, count=4)
        max_risk_score(threshold=0.3)
        max_mutations_per_epoch(count=5)
        freeze_tier(tier=SANDBOX)
        require_rule(rule_id=lineage_continuity, severity=BLOCKING)
        min_test_coverage(threshold=0.90)
        """
        policy = interpret_policy_block(block)
        assert policy.simulation is True
        assert policy.constraint_count == 6
        assert policy.require_approvals == {"tier": "PRODUCTION", "count": 4}
        assert policy.max_risk_score == pytest.approx(0.3)
        assert policy.max_mutations_per_epoch == 5
        assert "SANDBOX" in policy.freeze_tiers
        assert len(policy.require_rules) == 1
        assert policy.min_test_coverage == pytest.approx(0.90)

    def test_source_expressions_preserved(self):
        block = "max_risk_score(threshold=0.5)\nmax_mutations_per_epoch(count=3)"
        policy = interpret_policy_block(block)
        assert len(policy.source_expressions) == 2

    def test_grammar_version_preserved(self):
        policy = interpret_policy_block("max_risk_score(threshold=0.5)")
        assert policy.grammar_version == DSL_GRAMMAR_VERSION


# ---------------------------------------------------------------------------
# SimulationPolicy: to_dict() serialisation
# ---------------------------------------------------------------------------

class TestSimulationPolicyToDict:
    def test_to_dict_contains_simulation_true(self):
        policy = interpret_policy_block("max_risk_score(threshold=0.5)")
        d = policy.to_dict()
        assert d["simulation"] is True

    def test_to_dict_null_fields_present(self):
        policy = interpret_policy([])
        d = policy.to_dict()
        assert "require_approvals" in d
        assert d["require_approvals"] is None
        assert d["freeze_tiers"] == []
        assert d["require_rules"] == []

    def test_to_dict_is_deterministic(self):
        block = "max_risk_score(threshold=0.5)\nrequire_approvals(tier=PRODUCTION, count=2)"
        d1 = interpret_policy_block(block).to_dict()
        d2 = interpret_policy_block(block).to_dict()
        assert d1 == d2
