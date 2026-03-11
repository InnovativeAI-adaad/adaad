import pytest
pytestmark = pytest.mark.regression_standard
# SPDX-License-Identifier: Apache-2.0

from app.beast_mode_loop import LegacyBeastModeCompatibilityAdapter


def test_build_mutation_candidate_consumes_projection_inputs(tmp_path) -> None:
    adapter = LegacyBeastModeCompatibilityAdapter(agents_root=tmp_path / "agents", lineage_dir=tmp_path / "lineage")
    payload = {
        "mutation_id": "m-1",
        "expected_gain": 0.5,
        "risk_score": 0.2,
        "complexity": 0.1,
        "coverage_delta": 0.3,
        "strategic_horizon": 3,
        "forecast_roi": 1.2,
    }

    candidate, missing = adapter._build_mutation_candidate(payload)

    assert not missing
    assert candidate is not None
    assert candidate.strategic_horizon == 3.0
    assert candidate.forecast_roi == 1.2
