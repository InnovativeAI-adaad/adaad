# SPDX-License-Identifier: Apache-2.0
import pytest

from app.agents import base_agent

pytestmark = pytest.mark.regression_standard


def test_validate_agents_skips_hidden_paths_and_is_deterministic(monkeypatch, tmp_path):
    agents_root = tmp_path / "agents"
    agents_root.mkdir()

    hidden = agents_root / ".hidden_agent"
    dunder = agents_root / "__cache_agent"
    visible_missing = agents_root / "visible_missing"

    for path in (hidden, dunder, visible_missing):
        path.mkdir()

    def fake_iter_agent_dirs(_root):
        return [hidden, dunder, visible_missing]

    monkeypatch.setattr(base_agent, "iter_agent_dirs", fake_iter_agent_dirs)

    first_valid, first_errors = base_agent.validate_agents(agents_root)
    second_valid, second_errors = base_agent.validate_agents(agents_root)

    expected_errors = ["visible_missing: meta.json,dna.json,certificate.json"]
    assert first_valid is False
    assert second_valid is False
    assert first_errors == expected_errors
    assert second_errors == expected_errors
