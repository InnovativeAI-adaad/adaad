# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path


def test_runtime_api_agents_lazy_exports_resolve_core_symbols() -> None:
    from runtime.api import agents

    assert callable(agents.agent_path_from_id)
    assert agents.MutationRequest is not None
    assert agents.MutationTarget is not None


def test_runtime_api_package_lazy_exports_resolve_without_eager_cycles() -> None:
    import runtime.api as runtime_api

    assert runtime_api.MutationRequest is not None
    assert callable(runtime_api.resolve_agent_id)


def test_runtime_evolution_lazy_export_resolves_without_full_package_import() -> None:
    import runtime.evolution as evolution

    evaluator = evolution.EconomicFitnessEvaluator()
    result = evaluator.evaluate({"simulated_market_score": 0.5})

    assert result.simulated_market_score == 0.5
    assert Path("runtime/evolution/economic_fitness.py").exists()
