# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from app.dream_mode import DreamMode
import pytest

from runtime.governance.foundation import SeededDeterminismProvider, SystemDeterminismProvider


@mock.patch("app.dream_mode.cryovant.validate_ancestry", return_value=True)
@mock.patch("app.dream_mode.stage_offspring")
@mock.patch("app.dream_mode.agent_path_from_id", return_value=Path("/tmp/agent"))
def test_strict_mode_reproducible_mutation_content(_path, stage_offspring, _ancestry) -> None:
    provider = SeededDeterminismProvider(seed="dream-eq")
    dream = DreamMode(Path("/tmp"), Path("/tmp"), replay_mode="strict", provider=provider)
    dream.discover_tasks = mock.Mock(return_value=["sample_agent"])
    dream._read_json = mock.Mock(return_value={"dream_scope": {"enabled": True, "allow": ["mutation"]}})

    dream.run_cycle(agent_id="sample_agent", epoch_id="epoch-7", bundle_id="bundle-9")
    content_a = stage_offspring.call_args.kwargs["content"]

    dream.entropy_budget = dream.entropy_budget.__class__()
    dream.run_cycle(agent_id="sample_agent", epoch_id="epoch-7", bundle_id="bundle-9")
    content_b = stage_offspring.call_args.kwargs["content"]

    assert content_a == content_b


@mock.patch("app.dream_mode.cryovant.validate_ancestry", return_value=True)
@mock.patch("app.dream_mode.stage_offspring")
@mock.patch("app.dream_mode.agent_path_from_id", return_value=Path("/tmp/agent"))
def test_non_strict_mode_uses_provider_token_generation(_path, stage_offspring, _ancestry) -> None:
    provider = SeededDeterminismProvider(seed="legacy-compatible")
    dream = DreamMode(Path("/tmp"), Path("/tmp"), replay_mode="off", provider=provider)
    dream.discover_tasks = mock.Mock(return_value=["sample_agent"])
    dream._read_json = mock.Mock(return_value={"dream_scope": {"enabled": True, "allow": ["mutation"]}})

    dream.run_cycle(agent_id="sample_agent", epoch_id="epoch-1", bundle_id="bundle-a")

    content = stage_offspring.call_args.kwargs["content"]
    expected_token = provider.next_token(label="dream_token:epoch-1:sample_agent:bundle-a", length=16)
    assert content == f"sample_agent-mutation-{expected_token}"


@mock.patch("app.dream_mode.cryovant.validate_ancestry", return_value=True)
@mock.patch("app.dream_mode.stage_offspring")
@mock.patch("app.dream_mode.agent_path_from_id", return_value=Path("/tmp/agent"))
def test_handoff_issued_at_format_is_provider_backed(_path, stage_offspring, _ancestry) -> None:
    provider = SeededDeterminismProvider(seed="clock-seed", fixed_now=datetime(2027, 2, 3, 4, 5, 6, tzinfo=timezone.utc))
    dream = DreamMode(Path("/tmp"), Path("/tmp"), replay_mode="off", provider=provider)
    dream.discover_tasks = mock.Mock(return_value=["sample_agent"])
    dream._read_json = mock.Mock(return_value={"dream_scope": {"enabled": True, "allow": ["mutation"]}})

    dream.run_cycle(agent_id="sample_agent", epoch_id="epoch-3", bundle_id="bundle-c")

    handoff_contract = stage_offspring.call_args.kwargs["handoff_contract"]
    assert handoff_contract["issued_at"] == "2027-02-03T04:05:06Z"


@mock.patch("app.dream_mode.cryovant.validate_ancestry", return_value=True)
@mock.patch("app.dream_mode.agent_path_from_id", return_value=Path("/tmp/agent"))
def test_strict_mode_replay_equivalence_includes_handoff_metadata(_path, _ancestry) -> None:
    scope = {"dream_scope": {"enabled": True, "allow": ["mutation"]}}
    provider_a = SeededDeterminismProvider(seed="dream-handoff", fixed_now=datetime(2028, 6, 1, 2, 3, 4, tzinfo=timezone.utc))
    provider_b = SeededDeterminismProvider(seed="dream-handoff", fixed_now=datetime(2028, 6, 1, 2, 3, 4, tzinfo=timezone.utc))

    dream_a = DreamMode(Path("/tmp"), Path("/tmp"), replay_mode="strict", provider=provider_a)
    dream_b = DreamMode(Path("/tmp"), Path("/tmp"), replay_mode="strict", provider=provider_b)
    dream_a.discover_tasks = mock.Mock(return_value=["sample_agent"])
    dream_b.discover_tasks = mock.Mock(return_value=["sample_agent"])
    dream_a._read_json = mock.Mock(return_value=scope)
    dream_b._read_json = mock.Mock(return_value=scope)

    with mock.patch("app.dream_mode.stage_offspring") as stage_a:
        dream_a.run_cycle(agent_id="sample_agent", epoch_id="epoch-11", bundle_id="bundle-r")
        mutation_a = stage_a.call_args.kwargs["content"]
        handoff_a = stage_a.call_args.kwargs["handoff_contract"]

    with mock.patch("app.dream_mode.stage_offspring") as stage_b:
        dream_b.run_cycle(agent_id="sample_agent", epoch_id="epoch-11", bundle_id="bundle-r")
        mutation_b = stage_b.call_args.kwargs["content"]
        handoff_b = stage_b.call_args.kwargs["handoff_contract"]

    assert mutation_a == mutation_b
    assert handoff_a == handoff_b


def test_dream_mode_rejects_nondeterministic_provider_for_audit_and_strict() -> None:
    with pytest.raises(RuntimeError, match="strict_replay_requires_deterministic_provider"):
        DreamMode(Path("/tmp"), Path("/tmp"), replay_mode="strict", provider=SystemDeterminismProvider())

    with pytest.raises(RuntimeError, match="audit_tier_requires_deterministic_provider"):
        DreamMode(Path("/tmp"), Path("/tmp"), replay_mode="off", recovery_tier="audit", provider=SystemDeterminismProvider())
