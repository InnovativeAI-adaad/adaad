# SPDX-License-Identifier: Apache-2.0
"""Integration tests for runtime.innovations30.integration.InnovationsPipeline."""

from __future__ import annotations

from dataclasses import asdict

from runtime.innovations30.integration import InnovationsPipeline


def _deterministic_payload(mutation_id: str) -> dict:
    return {
        "mutation_id": mutation_id,
        "agent_id": "agent-integration-fixed",
        "intent": "Improve governance auditability without bypassing controls",
        "diff_text": (
            "--- a/runtime/metrics.py\n"
            "+++ b/runtime/metrics.py\n"
            "@@ -1,4 +1,4 @@\n"
            "-metrics.log('legacy')\n"
            "+metrics.log('improved')\n"
            "+# delete_test marker for deterministic warning coverage\n"
        ),
        "changed_files": ["runtime/metrics.py"],
        "before_source": "def f(x):\n    x = x + 1\n    return x\n",
        "after_source": "def f(x):\n    return x + 1\n",
        "epoch_id": "epoch-integration-2026-03-28",
        "epoch_seq": 42,
        "declared_semver": "patch",
        "base_fitness": 0.72,
        "recent_fitness_deltas": [0.01, 0.02, 0.01],
        "health_score": 0.80,
        "blocking_rules": ["lineage_continuity"],
        "overridden_rules": ["import_boundary"],
    }


def test_pipeline_component_coverage_is_represented_in_eval_output(tmp_path):
    pipeline = InnovationsPipeline(data_dir=tmp_path / "data")
    result = pipeline.evaluate_mutation(**_deterministic_payload("mut-int-0001"))

    component_names = set(pipeline.component_names())
    signal_map = result.component_signal_map

    assert set(signal_map.keys()) == component_names
    for component_name, channels in signal_map.items():
        assert channels, f"{component_name} missing output representation"
        assert set(channels).issubset({"direct", "warning", "blocking"})


def test_pipeline_repeatability_same_input_same_output(tmp_path):
    payload = _deterministic_payload("mut-int-0002")

    result_a = InnovationsPipeline(data_dir=tmp_path / "run-a").evaluate_mutation(**payload)
    result_b = InnovationsPipeline(data_dir=tmp_path / "run-b").evaluate_mutation(**payload)

    assert asdict(result_a) == asdict(result_b)


def test_blocking_signals_dominate_and_are_not_downgraded_to_warning(tmp_path):
    pipeline = InnovationsPipeline(data_dir=tmp_path / "data")
    pipeline._init()
    bankruptcy = pipeline.get_component("bankruptcy")
    bankruptcy.evaluate(
        epoch_id="epoch-bankruptcy-2026-03-28",
        debt_score=1.0,
        health_score=0.1,
    )

    payload = _deterministic_payload("mut-int-0003")
    payload["intent"] = "Optimize throughput only"
    payload["diff_text"] = (
        "--- a/runtime/metrics.py\n"
        "+++ b/runtime/metrics.py\n"
        "@@ -1,3 +1,2 @@\n"
        "-metrics.log('legacy')\n"
        "+return 0\n"
    )

    result = pipeline.evaluate_mutation(**payload)

    assert result.blocking_violations, "Expected blocking violations from safety invariants"
    assert result.component_signal_map["self_aware"].count("blocking") >= 1
    assert result.component_signal_map["bankruptcy"].count("blocking") >= 1

    blocking_text = "\n".join(result.blocking_violations)
    warnings_text = "\n".join(result.warnings)
    assert "SELF-AWARE-0" in blocking_text
    assert "BANKRUPTCY ACTIVE" in blocking_text
    assert "SELF-AWARE-0" not in warnings_text
    assert "BANKRUPTCY ACTIVE" not in warnings_text
