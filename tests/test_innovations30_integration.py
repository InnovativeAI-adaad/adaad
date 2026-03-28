# SPDX-License-Identifier: Apache-2.0
"""Integration coverage for runtime.innovations30.integration."""
from __future__ import annotations

from runtime.innovations30.integration import InnovationsPipeline


def test_evaluate_mutation_populates_extended_component_fields(tmp_path):
    pipeline = InnovationsPipeline(data_dir=tmp_path)

    result = pipeline.evaluate_mutation(
        mutation_id="m-100",
        agent_id="agent-1",
        intent="improve safety checks",
        diff_text="+def guard():\n+    return True",
        changed_files=["runtime/safety/checks.py"],
        before_source="def guard():\n    return False",
        after_source="def guard():\n    return True",
        epoch_id="epoch-100",
        epoch_seq=10,
        blocking_rules=["lineage_continuity"],
        overridden_rules=["single_file_scope"],
    )

    assert result.temporal_governance_ruleset
    assert isinstance(result.invariant_discoveries, list)
    assert isinstance(result.rule_calibration_summary, dict)
    assert result.temporal_regret_registered is True
    assert isinstance(result.epistemic_decay_summary, dict)
    assert isinstance(result.dream_candidate_ids, list)
    assert isinstance(result.genealogy_productive_lineages, list)
    assert isinstance(result.genealogy_dead_end_epochs, list)
    assert isinstance(result.genealogy_direction, dict)
    assert isinstance(result.jury_dissent_count, int)
    assert isinstance(result.staking_balance, float)
    assert isinstance(result.staking_win_rate, float)
    assert isinstance(result.postmortem_recurring_gaps, dict)
    assert isinstance(result.archaeology_event_count, int)
    assert result.stress_cases_tested > 0
    assert isinstance(result.market_adjusted_score, float)
    assert isinstance(result.market_health_score, float)
    assert isinstance(result.hardware_weights, dict)
    assert isinstance(result.entropy_drift_ratio, float)
    assert isinstance(result.mirror_test_due, bool)


def test_evaluate_mutation_is_deterministic_for_identical_inputs(tmp_path):
    pipeline = InnovationsPipeline(data_dir=tmp_path)
    kwargs = dict(
        mutation_id="m-det-1",
        agent_id="agent-det",
        intent="improve observability",
        diff_text="+x = 1",
        changed_files=["adaad/agents/example.py"],
        before_source="x = 0",
        after_source="x = 1",
        epoch_id="epoch-det-1",
        epoch_seq=7,
    )

    first = pipeline.evaluate_mutation(**kwargs)
    second = pipeline.evaluate_mutation(**kwargs)

    assert first.overall_innovations_score == second.overall_innovations_score
    assert first.temporal_governance_ruleset == second.temporal_governance_ruleset
    assert first.market_adjusted_score == second.market_adjusted_score
    assert first.hardware_adapted_score == second.hardware_adapted_score
    assert first.stress_cases_tested == second.stress_cases_tested
    assert first.stress_gaps_found == second.stress_gaps_found
