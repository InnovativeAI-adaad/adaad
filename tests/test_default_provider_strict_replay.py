# SPDX-License-Identifier: Apache-2.0
"""Tests for default_provider() strict replay mode enforcement."""

import pytest
pytestmark = pytest.mark.regression_standard

from runtime.governance.foundation.determinism import SeededDeterminismProvider, SystemDeterminismProvider, default_provider


def test_default_provider_returns_system_provider_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ADAAD_FORCE_DETERMINISTIC_PROVIDER", raising=False)
    monkeypatch.delenv("ADAAD_REPLAY_MODE", raising=False)
    monkeypatch.delenv("ADAAD_DETERMINISTIC_SEED", raising=False)
    provider = default_provider()
    assert isinstance(provider, SystemDeterminismProvider)
    assert not provider.deterministic


def test_default_provider_returns_seeded_when_force_flag_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_FORCE_DETERMINISTIC_PROVIDER", "1")
    monkeypatch.setenv("ADAAD_DETERMINISTIC_SEED", "test-seed")
    monkeypatch.delenv("ADAAD_REPLAY_MODE", raising=False)
    provider = default_provider()
    assert isinstance(provider, SeededDeterminismProvider)
    assert provider.deterministic


def test_default_provider_strict_replay_without_seed_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_REPLAY_MODE", "strict")
    monkeypatch.delenv("ADAAD_DETERMINISTIC_SEED", raising=False)
    monkeypatch.delenv("ADAAD_FORCE_DETERMINISTIC_PROVIDER", raising=False)
    with pytest.raises(RuntimeError, match="ADAAD_DETERMINISTIC_SEED"):
        default_provider()


def test_default_provider_strict_replay_with_seed_returns_seeded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAAD_REPLAY_MODE", "strict")
    monkeypatch.setenv("ADAAD_DETERMINISTIC_SEED", "replay-seed-001")
    monkeypatch.delenv("ADAAD_FORCE_DETERMINISTIC_PROVIDER", raising=False)
    provider = default_provider()
    assert isinstance(provider, SeededDeterminismProvider)
    assert provider.deterministic
    assert provider.seed == "replay-seed-001"


def test_default_provider_non_strict_replay_mode_returns_system(monkeypatch: pytest.MonkeyPatch) -> None:
    for mode in ("off", "", "soft", "OFF"):
        monkeypatch.setenv("ADAAD_REPLAY_MODE", mode)
        monkeypatch.delenv("ADAAD_FORCE_DETERMINISTIC_PROVIDER", raising=False)
        monkeypatch.delenv("ADAAD_DETERMINISTIC_SEED", raising=False)
        provider = default_provider()
        assert isinstance(provider, SystemDeterminismProvider)
