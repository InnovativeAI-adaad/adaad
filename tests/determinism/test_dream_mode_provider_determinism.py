# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest
pytestmark = pytest.mark.autonomous_critical

from runtime.governance.foundation import SeededDeterminismProvider, SystemDeterminismProvider


def _dream_mode_cls():
    pytest.importorskip("yaml")
    from app.dream_mode import DreamMode

    return DreamMode


def _create_agent_fixture(agents_root: Path, agent_id: str = "sample_agent") -> None:
    agent_dir = agents_root / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "meta.json").write_text('{"dream_scope": {"enabled": true, "allow": ["mutation"]}}\n', encoding="utf-8")
    (agent_dir / "dna.json").write_text("{}\n", encoding="utf-8")
    (agent_dir / "certificate.json").write_text("{}\n", encoding="utf-8")


def test_strict_mode_reproducible_mutation_content(tmp_path: Path) -> None:
    _create_agent_fixture(tmp_path)
    provider = SeededDeterminismProvider(seed="dream-eq")
    DreamMode = _dream_mode_cls()
    dream = DreamMode(tmp_path, tmp_path / "lineage", replay_mode="strict", provider=provider)

    with mock.patch("app.dream_mode.cryovant.validate_ancestry", return_value=True), mock.patch("app.dream_mode.stage_offspring") as stage_offspring:
        dream.run_cycle(agent_id="sample_agent", epoch_id="epoch-7", bundle_id="bundle-9")
        content_a = stage_offspring.call_args.kwargs["content"]

        dream.entropy_budget = dream.entropy_budget.__class__()
        dream.run_cycle(agent_id="sample_agent", epoch_id="epoch-7", bundle_id="bundle-9")
        content_b = stage_offspring.call_args.kwargs["content"]

    assert content_a == content_b


def test_non_strict_mode_uses_provider_token_generation(tmp_path: Path) -> None:
    _create_agent_fixture(tmp_path)
    provider = SeededDeterminismProvider(seed="legacy-compatible")
    DreamMode = _dream_mode_cls()
    dream = DreamMode(tmp_path, tmp_path / "lineage", replay_mode="off", provider=provider)

    with mock.patch("app.dream_mode.cryovant.validate_ancestry", return_value=True), mock.patch("app.dream_mode.stage_offspring") as stage_offspring:
        dream.run_cycle(agent_id="sample_agent", epoch_id="epoch-1", bundle_id="bundle-a")

        content = stage_offspring.call_args.kwargs["content"]
    from runtime.evolution.entropy_discipline import deterministic_token
    expected_token = deterministic_token(
        epoch_id="epoch-1",
        bundle_id="bundle-a",
        agent_id="sample_agent",
        label="dream_token",
        length=16,
    )
    assert content == f"sample_agent-mutation-{expected_token}"


def test_handoff_issued_at_format_is_provider_backed(tmp_path: Path) -> None:
    _create_agent_fixture(tmp_path)
    provider = SeededDeterminismProvider(seed="clock-seed", fixed_now=datetime(2027, 2, 3, 4, 5, 6, tzinfo=timezone.utc))
    DreamMode = _dream_mode_cls()
    dream = DreamMode(tmp_path, tmp_path / "lineage", replay_mode="off", provider=provider)

    with mock.patch("app.dream_mode.cryovant.validate_ancestry", return_value=True), mock.patch("app.dream_mode.stage_offspring") as stage_offspring:
        dream.run_cycle(agent_id="sample_agent", epoch_id="epoch-3", bundle_id="bundle-c")

        handoff_contract = stage_offspring.call_args.kwargs["handoff_contract"]
    assert handoff_contract["issued_at"] == "2027-02-03T04:05:06Z"


def test_strict_mode_replay_equivalence_includes_handoff_metadata(tmp_path: Path) -> None:
    _create_agent_fixture(tmp_path)
    DreamMode = _dream_mode_cls()
    provider_a = SeededDeterminismProvider(seed="dream-handoff", fixed_now=datetime(2028, 6, 1, 2, 3, 4, tzinfo=timezone.utc))
    provider_b = SeededDeterminismProvider(seed="dream-handoff", fixed_now=datetime(2028, 6, 1, 2, 3, 4, tzinfo=timezone.utc))

    dream_a = DreamMode(tmp_path, tmp_path / "lineage-a", replay_mode="strict", provider=provider_a)
    dream_b = DreamMode(tmp_path, tmp_path / "lineage-b", replay_mode="strict", provider=provider_b)

    with mock.patch("app.dream_mode.cryovant.validate_ancestry", return_value=True), mock.patch("app.dream_mode.stage_offspring") as stage_a:
        dream_a.run_cycle(agent_id="sample_agent", epoch_id="epoch-11", bundle_id="bundle-r")
        mutation_a = stage_a.call_args.kwargs["content"]
        handoff_a = stage_a.call_args.kwargs["handoff_contract"]

    with mock.patch("app.dream_mode.cryovant.validate_ancestry", return_value=True), mock.patch("app.dream_mode.stage_offspring") as stage_b:
        dream_b.run_cycle(agent_id="sample_agent", epoch_id="epoch-11", bundle_id="bundle-r")
        mutation_b = stage_b.call_args.kwargs["content"]
        handoff_b = stage_b.call_args.kwargs["handoff_contract"]

    assert mutation_a == mutation_b
    assert handoff_a == handoff_b


def test_dream_mode_rejects_nondeterministic_provider_for_audit_and_strict() -> None:
    DreamMode = _dream_mode_cls()
    with pytest.raises(RuntimeError, match="strict_replay_requires_deterministic_provider"):
        DreamMode(Path("/tmp"), Path("/tmp"), replay_mode="strict", provider=SystemDeterminismProvider())

    with pytest.raises(RuntimeError, match="audit_tier_requires_deterministic_provider"):
        DreamMode(Path("/tmp"), Path("/tmp"), replay_mode="off", recovery_tier="audit", provider=SystemDeterminismProvider())

    with pytest.raises(RuntimeError, match="audit_tier_requires_deterministic_provider"):
        DreamMode(Path("/tmp"), Path("/tmp"), replay_mode="off", recovery_tier="governance", provider=SystemDeterminismProvider())

    with pytest.raises(RuntimeError, match="audit_tier_requires_deterministic_provider"):
        DreamMode(Path("/tmp"), Path("/tmp"), replay_mode="off", recovery_tier="critical", provider=SystemDeterminismProvider())


def test_discover_tasks_logs_summary_payload_by_default(tmp_path: Path) -> None:
    _create_agent_fixture(tmp_path, agent_id="agent_b")
    _create_agent_fixture(tmp_path, agent_id="agent_a")
    DreamMode = _dream_mode_cls()
    dream = DreamMode(tmp_path, tmp_path / "lineage", replay_mode="strict", provider=SeededDeterminismProvider(seed="metrics"))

    with mock.patch("app.dream_mode.metrics.log") as log_metric:
        tasks = dream.discover_tasks()

    assert tasks == ["agent_a", "agent_b"]
    log_metric.assert_called_once()
    kwargs = log_metric.call_args.kwargs
    assert kwargs["event_type"] == "dream_discovery"
    assert kwargs["payload"] == {"task_count": 2, "task_sample": ["agent_a", "agent_b"]}


def test_discover_tasks_debug_flag_allows_full_task_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _create_agent_fixture(tmp_path, agent_id="agent_c")
    _create_agent_fixture(tmp_path, agent_id="agent_a")
    _create_agent_fixture(tmp_path, agent_id="agent_b")
    monkeypatch.setenv("ADAAD_METRICS_INCLUDE_FULL_TASKS", "1")
    monkeypatch.setenv("ADAAD_DREAM_DISCOVERY_SAMPLE_SIZE", "2")

    DreamMode = _dream_mode_cls()
    dream = DreamMode(tmp_path, tmp_path / "lineage", replay_mode="strict", provider=SeededDeterminismProvider(seed="metrics-debug"))

    with mock.patch("app.dream_mode.metrics.log") as log_metric:
        tasks = dream.discover_tasks()

    assert tasks == ["agent_a", "agent_b", "agent_c"]
    payload = log_metric.call_args.kwargs["payload"]
    assert payload["task_count"] == 3
    assert payload["task_sample"] == ["agent_a", "agent_b"]
    assert payload["tasks"] == ["agent_a", "agent_b", "agent_c"]


def test_discover_tasks_invalid_sample_env_falls_back_to_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _create_agent_fixture(tmp_path, agent_id="agent_d")
    _create_agent_fixture(tmp_path, agent_id="agent_c")
    _create_agent_fixture(tmp_path, agent_id="agent_b")
    _create_agent_fixture(tmp_path, agent_id="agent_a")
    monkeypatch.setenv("ADAAD_DREAM_DISCOVERY_SAMPLE_SIZE", "not-an-int")

    DreamMode = _dream_mode_cls()
    dream = DreamMode(tmp_path, tmp_path / "lineage", replay_mode="strict", provider=SeededDeterminismProvider(seed="metrics-invalid-sample"))

    with mock.patch("app.dream_mode.metrics.log") as log_metric:
        tasks = dream.discover_tasks()

    assert tasks == ["agent_a", "agent_b", "agent_c", "agent_d"]
    payload = log_metric.call_args.kwargs["payload"]
    assert payload["task_count"] == 4
    assert payload["task_sample"] == ["agent_a", "agent_b", "agent_c"]
    assert "tasks" not in payload
