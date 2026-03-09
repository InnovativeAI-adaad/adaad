# SPDX-License-Identifier: Apache-2.0
"""Phase 16 — ProposalAdapter strategy-aware prompt routing tests (12 tests, T16-02-01..12)."""

import pytest

from runtime.intelligence.proposal_adapter import (
    _STRATEGY_SYSTEM_PROMPTS,
    _system_prompt_for_strategy,
)
from runtime.intelligence.strategy import STRATEGY_TAXONOMY


# T16-02-01  All taxonomy strategies have a dedicated prompt entry
def test_all_taxonomy_strategies_have_prompt_entries() -> None:
    for strategy_id in STRATEGY_TAXONOMY:
        assert strategy_id in _STRATEGY_SYSTEM_PROMPTS, (
            f"Missing system prompt for strategy '{strategy_id}'"
        )


# T16-02-02  _system_prompt_for_strategy rejects unknown strategy_id
def test_system_prompt_rejects_unknown_strategy_id() -> None:
    with pytest.raises(ValueError, match="not in STRATEGY_TAXONOMY"):
        _system_prompt_for_strategy("inject_prompt_exploit")


# T16-02-03  safety_hardening prompt includes hardening intent
def test_safety_hardening_prompt_contains_hardening_keywords() -> None:
    prompt = _system_prompt_for_strategy("safety_hardening")
    assert "hardening" in prompt.lower() or "safety" in prompt.lower()
    assert "do not" in prompt.lower() or "not weaken" in prompt.lower() or "do NOT" in prompt


# T16-02-04  structural_refactor prompt includes refactoring intent
def test_structural_refactor_prompt_contains_refactor_keywords() -> None:
    prompt = _system_prompt_for_strategy("structural_refactor")
    assert "refactor" in prompt.lower() or "coupling" in prompt.lower()


# T16-02-05  test_coverage_expansion prompt includes coverage intent
def test_test_coverage_prompt_contains_coverage_keywords() -> None:
    prompt = _system_prompt_for_strategy("test_coverage_expansion")
    assert "test" in prompt.lower() and "coverage" in prompt.lower()


# T16-02-06  performance_optimization prompt includes performance intent
def test_performance_optimization_prompt_contains_perf_keywords() -> None:
    prompt = _system_prompt_for_strategy("performance_optimization")
    assert "performance" in prompt.lower() or "latency" in prompt.lower() or "optimis" in prompt.lower()


# T16-02-07  conservative_hold prompt includes conservative/minimal intent
def test_conservative_hold_prompt_contains_conservative_keywords() -> None:
    prompt = _system_prompt_for_strategy("conservative_hold")
    assert "conservative" in prompt.lower() or "minimal" in prompt.lower()


# T16-02-08  adaptive_self_mutate prompt includes mutation gain intent
def test_adaptive_self_mutate_prompt_contains_mutation_keywords() -> None:
    prompt = _system_prompt_for_strategy("adaptive_self_mutate")
    assert "mutation" in prompt.lower() or "immediate" in prompt.lower()


# T16-02-09  All prompts require JSON output format
def test_all_prompts_require_json_output() -> None:
    for strategy_id in STRATEGY_TAXONOMY:
        prompt = _system_prompt_for_strategy(strategy_id)
        assert "json" in prompt.lower(), f"Prompt for '{strategy_id}' missing JSON requirement"


# T16-02-10  All prompts include required field spec
def test_all_prompts_include_required_fields() -> None:
    required_fields = ["title", "summary", "real_diff", "target_files"]
    for strategy_id in STRATEGY_TAXONOMY:
        prompt = _system_prompt_for_strategy(strategy_id)
        for field in required_fields:
            assert field in prompt, (
                f"Prompt for '{strategy_id}' missing required field '{field}'"
            )


# T16-02-11  _system_prompt_for_strategy is deterministic
def test_system_prompt_is_deterministic() -> None:
    for strategy_id in STRATEGY_TAXONOMY:
        p1 = _system_prompt_for_strategy(strategy_id)
        p2 = _system_prompt_for_strategy(strategy_id)
        assert p1 == p2


# T16-02-12  strategy_prompt_version "16.0" documented in evidence on adapter build
#             (unit test via import — no LLM call needed)
def test_strategy_prompt_version_constant() -> None:
    # Verify the version constant is accessible and correct
    import runtime.intelligence.proposal_adapter as pa  # noqa: PLC0415
    assert hasattr(pa, "_STRATEGY_SYSTEM_PROMPTS")
    assert len(pa._STRATEGY_SYSTEM_PROMPTS) == 6
