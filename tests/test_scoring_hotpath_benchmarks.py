# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import time

from runtime.autonomy.mutation_scaffold import MutationCandidate, rank_mutation_candidates
from runtime.fitness_pipeline import FitnessPipeline, RiskEvaluator, TestOutcomeEvaluator


def test_benchmark_mutation_scaffold_repeated_candidate_extraction() -> None:
    candidates = [
        MutationCandidate(
            mutation_id=f"m-{i}",
            expected_gain=0.8,
            risk_score=0.3,
            complexity=0.2,
            coverage_delta=0.4,
            python_content="def f(x):\n    return x + 1\n",
            source_context_hash=f"ctx-{i%8}",
            generation=i % 3,
            parent_id=("p" if i % 2 == 0 else None),
        )
        for i in range(200)
    ]

    start = time.perf_counter()
    first = rank_mutation_candidates(candidates)
    first_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    second = rank_mutation_candidates(candidates)
    second_elapsed = time.perf_counter() - start

    assert [s.mutation_id for s in first] == [s.mutation_id for s in second]
    assert first_elapsed > 0.0
    assert second_elapsed > 0.0


def test_benchmark_fitness_pipeline_repeated_payload_hashing() -> None:
    pipeline = FitnessPipeline([TestOutcomeEvaluator(), RiskEvaluator()])
    payload = {
        "tests_ok": True,
        "impact_risk_score": 0.12,
        "epoch_id": "epoch-bench",
        "mutation_id": "bench-1",
        "mutation_tier": "medium",
        "goal_alignment_score": 0.6,
    }

    start = time.perf_counter()
    r1 = pipeline.evaluate(dict(payload))
    first_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    r2 = pipeline.evaluate(dict(payload))
    second_elapsed = time.perf_counter() - start

    assert r1["material_hash"] == r2["material_hash"]
    assert r1["orchestrator"] == r2["orchestrator"]
    assert first_elapsed > 0.0
    assert second_elapsed > 0.0
