# SPDX-License-Identifier: Apache-2.0
"""
Phase 40 — BeastModeLoop RuntimeDeterminismProvider injection tests.

Mirrors the structure of test_dream_mode_provider_determinism.py (Phase 39).

Test IDs follow the Phase 40 scheme: T40-B01 .. T40-B12.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest

from runtime.governance.foundation import SeededDeterminismProvider, SystemDeterminismProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _beast_cls():
    from app.beast_mode_loop import BeastModeLoop
    return BeastModeLoop


def _patched_run(beast, agent_id: str = "sample_agent"):
    """Run a cycle with all external side-effects patched away."""
    with (
        mock.patch("app.beast_mode_loop.cryovant.validate_ancestry", return_value=False),
        mock.patch("app.beast_mode_loop.metrics.log"),
    ):
        return beast.run_cycle(agent_id=agent_id)


# ---------------------------------------------------------------------------
# T40-B01  Default (no provider kwarg) → SystemDeterminismProvider accepted
# ---------------------------------------------------------------------------

def test_default_construction_uses_system_provider(tmp_path: Path) -> None:
    """T40-B01: Omitting provider gives SystemDeterminismProvider (backward compat)."""
    BeastModeLoop = _beast_cls()
    beast = BeastModeLoop(tmp_path, tmp_path / "lineage")
    assert isinstance(beast._provider, SystemDeterminismProvider)


# ---------------------------------------------------------------------------
# T40-B02  SeededDeterminismProvider injected — _now() is deterministic
# ---------------------------------------------------------------------------

def test_seeded_provider_now_is_deterministic(tmp_path: Path) -> None:
    """T40-B02: _now() delegates to provider.now_utc()."""
    fixed = datetime(2027, 3, 15, 10, 20, 30, tzinfo=timezone.utc)
    provider = SeededDeterminismProvider(seed="beast-clock", fixed_now=fixed)
    BeastModeLoop = _beast_cls()
    beast = BeastModeLoop(tmp_path, tmp_path / "lineage", provider=provider)

    t = beast._now()
    assert t == fixed.timestamp()


# ---------------------------------------------------------------------------
# T40-B03  Strict replay mode with SeededProvider accepted
# ---------------------------------------------------------------------------

def test_strict_replay_with_seeded_provider_accepted(tmp_path: Path) -> None:
    """T40-B03: replay_mode='strict' + SeededDeterminismProvider constructs without error."""
    BeastModeLoop = _beast_cls()
    provider = SeededDeterminismProvider(seed="strict-ok")
    beast = BeastModeLoop(tmp_path, tmp_path / "lineage", replay_mode="strict", provider=provider)
    assert beast._replay_mode == "strict"


# ---------------------------------------------------------------------------
# T40-B04  Strict replay mode rejects SystemDeterminismProvider at construction
# ---------------------------------------------------------------------------

def test_strict_replay_rejects_system_provider() -> None:
    """T40-B04: replay_mode='strict' + SystemDeterminismProvider raises RuntimeError."""
    BeastModeLoop = _beast_cls()
    with pytest.raises(RuntimeError, match="strict_replay_requires_deterministic_provider"):
        BeastModeLoop(
            Path("/tmp"),
            Path("/tmp"),
            replay_mode="strict",
            provider=SystemDeterminismProvider(),
        )


# ---------------------------------------------------------------------------
# T40-B05  Audit tier rejects SystemDeterminismProvider at construction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tier", ["audit", "governance", "critical"])
def test_governance_tier_rejects_system_provider(tier: str) -> None:
    """T40-B05: governance-critical tiers raise with SystemDeterminismProvider."""
    BeastModeLoop = _beast_cls()
    with pytest.raises(RuntimeError, match="audit_tier_requires_deterministic_provider"):
        BeastModeLoop(
            Path("/tmp"),
            Path("/tmp"),
            recovery_tier=tier,
            provider=SystemDeterminismProvider(),
        )


# ---------------------------------------------------------------------------
# T40-B06  Audit tier auto-provisions SeededProvider when none supplied
# ---------------------------------------------------------------------------

def test_audit_tier_auto_provisions_seeded_provider(tmp_path: Path, monkeypatch) -> None:
    """T40-B06: audit tier without explicit provider gets SeededDeterminismProvider."""
    monkeypatch.setenv("ADAAD_DETERMINISTIC_SEED", "auto-audit-seed")
    BeastModeLoop = _beast_cls()
    beast = BeastModeLoop(tmp_path, tmp_path / "lineage", recovery_tier="audit")
    assert isinstance(beast._provider, SeededDeterminismProvider)


# ---------------------------------------------------------------------------
# T40-B07  Two instances with identical SeededProvider produce identical _now()
# ---------------------------------------------------------------------------

def test_identical_seeded_providers_produce_identical_now(tmp_path: Path) -> None:
    """T40-B07: Replay equivalence — same seed+fixed_now → same _now() timestamp."""
    fixed = datetime(2028, 1, 1, tzinfo=timezone.utc)
    BeastModeLoop = _beast_cls()
    a = BeastModeLoop(tmp_path, tmp_path / "lineage-a", provider=SeededDeterminismProvider(seed="eq", fixed_now=fixed))
    b = BeastModeLoop(tmp_path, tmp_path / "lineage-b", provider=SeededDeterminismProvider(seed="eq", fixed_now=fixed))
    assert a._now() == b._now()


# ---------------------------------------------------------------------------
# T40-B08  _check_limits() persists cooldown_until from provider clock
# ---------------------------------------------------------------------------

def test_check_limits_writes_provider_time_on_budget_exceeded(tmp_path: Path) -> None:
    """T40-B08: cooldown_until written by _check_limits is derived from provider clock."""
    import json as _json

    fixed = datetime(2028, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    provider = SeededDeterminismProvider(seed="budget-ts", fixed_now=fixed)
    BeastModeLoop = _beast_cls()

    # agents_root.parent == tmp_path, so state lives at tmp_path/data/
    agents_root = tmp_path / "agents"
    agents_root.mkdir(parents=True, exist_ok=True)

    beast = BeastModeLoop(agents_root, tmp_path / "lineage", provider=provider)
    beast.cycle_budget = 1  # Budget of 1 → exceeded once cycle_count reaches 1

    # Pre-populate state: cycle_count already at budget
    state_dir = tmp_path / "data"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "beast_mode_state.json").write_text(
        _json.dumps({
            "cycle_window_start": fixed.timestamp(),
            "cycle_count": 1.0,
            "mutation_window_start": 0.0,
            "mutation_count": 0.0,
            "cooldown_until": 0.0,
        }),
        encoding="utf-8",
    )

    with mock.patch("app.beast_mode_loop.metrics.log"):
        result = beast._check_limits()

    assert result is not None
    assert result["reason"] == "cycle_budget"
    state = beast._load_state()
    expected_cooldown = fixed.timestamp() + beast.cooldown_sec
    assert state["cooldown_until"] == pytest.approx(expected_cooldown, abs=1.0)


# ---------------------------------------------------------------------------
# T40-B09  _check_mutation_quota() uses provider clock for window refresh
# ---------------------------------------------------------------------------

def test_check_mutation_quota_uses_provider_clock(tmp_path: Path) -> None:
    """T40-B09: mutation quota enforcement reads time from provider.now_utc()."""
    import json as _json

    fixed = datetime(2028, 7, 4, 12, 0, 0, tzinfo=timezone.utc)
    provider = SeededDeterminismProvider(seed="quota-ts", fixed_now=fixed)
    BeastModeLoop = _beast_cls()

    agents_root = tmp_path / "agents"
    agents_root.mkdir(parents=True, exist_ok=True)

    beast = BeastModeLoop(agents_root, tmp_path / "lineage", provider=provider)
    beast.mutation_quota = 1

    state_dir = tmp_path / "data"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "beast_mode_state.json").write_text(
        _json.dumps({
            "cycle_window_start": 0.0,
            "cycle_count": 0.0,
            "mutation_window_start": fixed.timestamp(),
            "mutation_count": 1.0,
            "cooldown_until": 0.0,
        }),
        encoding="utf-8",
    )

    with mock.patch("app.beast_mode_loop.metrics.log"):
        result = beast._check_mutation_quota()

    assert result is not None
    assert result["reason"] == "mutation_quota"
    state = beast._load_state()
    expected_cooldown = fixed.timestamp() + beast.cooldown_sec
    assert state["cooldown_until"] == pytest.approx(expected_cooldown, abs=1.0)


# ---------------------------------------------------------------------------
# T40-B10  replay_mode stored on instance
# ---------------------------------------------------------------------------

def test_replay_mode_stored_on_instance(tmp_path: Path) -> None:
    """T40-B10: _replay_mode attribute reflects constructor arg."""
    BeastModeLoop = _beast_cls()
    for mode in ("off", "strict"):
        provider = SeededDeterminismProvider(seed="mode-check") if mode == "strict" else None
        beast = BeastModeLoop(tmp_path, tmp_path / "lineage", replay_mode=mode, provider=provider)
        assert beast._replay_mode == mode


# ---------------------------------------------------------------------------
# T40-B11  recovery_tier stored on instance (normalised to lower-case)
# ---------------------------------------------------------------------------

def test_recovery_tier_stored_on_instance(tmp_path: Path) -> None:
    """T40-B11: _recovery_tier normalised and stored."""
    BeastModeLoop = _beast_cls()
    beast = BeastModeLoop(
        tmp_path,
        tmp_path / "lineage",
        recovery_tier="Audit",
        provider=SeededDeterminismProvider(seed="tier-store"),
    )
    assert beast._recovery_tier == "audit"


# ---------------------------------------------------------------------------
# T40-B12  LegacyBeastModeCompatibilityAdapter inherits provider injection
# ---------------------------------------------------------------------------

def test_legacy_adapter_inherits_provider_injection(tmp_path: Path) -> None:
    """T40-B12: LegacyBeastModeCompatibilityAdapter accepts provider kwarg via super().__init__."""
    from app.beast_mode_loop import LegacyBeastModeCompatibilityAdapter

    provider = SeededDeterminismProvider(seed="legacy-inject")
    adapter = LegacyBeastModeCompatibilityAdapter(
        tmp_path, tmp_path / "lineage", provider=provider
    )
    assert adapter._provider is provider
    assert isinstance(adapter._provider, SeededDeterminismProvider)
